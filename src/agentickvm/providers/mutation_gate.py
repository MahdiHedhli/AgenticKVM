"""Verified-clearance handles that gate every concrete mutating transport.

The mutating live transports are a separate explicit path from the
structurally GET-only read layer. They refuse to actuate unless handed a
``VerifiedMutationClearance`` — an unforgeable handle that can only be issued
by :func:`issue_verified_mutation_clearance` after the existing ACT clearance
verification (Ed25519 proof, params-fingerprint parity, identity binding,
expiry) has passed. Handles are single-use per transport via
:class:`MutationClearanceLedger`, so a cleared action cannot be replayed.

This module is socket-free: it performs no I/O, resolves no credentials, and
its refusal messages never include parameter values, fingerprints, or target
details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, Protocol

from agentickvm.control_plane.fingerprints import fingerprint_parameters
from agentickvm.providers.errors import ProviderMutationBlockedError

# Module-private issuance token: handles constructed without it fail closed,
# so a VerifiedMutationClearance cannot be forged by direct construction or
# duck typing.
_ISSUER_TOKEN = object()

_REFUSED_CAPABILITY_PREFIXES = ("observe.",)
_REFUSED_CAPABILITY_IDS = frozenset({"provider.status"})


class ClearanceVerifierSeam(Protocol):
    """The existing ACT clearance verification seam (``ACTClearanceVerifier``)."""

    def verify(self, *, request: Any, response: Any, now: datetime) -> Any:
        """Return a verification result with ``valid`` and ``reason``."""


@dataclass(frozen=True)
class VerifiedMutationClearance:
    """Proof-verified, single-use authorization for exactly one mutating call.

    Instances exist only after the ACT clearance verifier accepted the
    response (cleared status, Ed25519 proof, params-fingerprint parity,
    request/response identity binding, expiry). The bound fields are re-checked
    at actuation time by :func:`require_verified_mutation_clearance`.
    """

    request_id: str
    capability: str
    target: str
    provider: str
    params_fingerprint: str
    risk_family: str
    expires_at: datetime
    tower_id: str | None
    issued_at: datetime
    issuer: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.issuer is not _ISSUER_TOKEN:
            raise ProviderMutationBlockedError(
                "mutation clearance handles can only be issued through "
                "verified clearance issuance"
            )
        required = {
            "request_id": self.request_id,
            "capability": self.capability,
            "target": self.target,
            "provider": self.provider,
            "params_fingerprint": self.params_fingerprint,
            "risk_family": self.risk_family,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ProviderMutationBlockedError(
                "mutation clearance handle is missing required bound fields"
            )
        if self.expires_at.tzinfo is None or self.issued_at.tzinfo is None:
            raise ProviderMutationBlockedError(
                "mutation clearance timestamps must be timezone-aware"
            )


class MutationClearanceLedger:
    """Track consumed clearance handles so mutating calls are single-use."""

    def __init__(self) -> None:
        self._consumed: set[str] = set()

    def consume(self, clearance: object, *, now: datetime | None) -> None:
        """Consume a handle exactly once; refuse replays and expiry fail-closed."""

        if not isinstance(clearance, VerifiedMutationClearance):
            raise ProviderMutationBlockedError(
                "mutating operations require a verified mutation clearance handle"
            )
        if now is None:
            raise ProviderMutationBlockedError(
                "mutation clearance consumption requires the current time"
            )
        if now.astimezone(UTC) >= clearance.expires_at.astimezone(UTC):
            raise ProviderMutationBlockedError("mutation clearance expired")
        if clearance.request_id in self._consumed:
            raise ProviderMutationBlockedError(
                "mutation clearance replay refused; handles are single-use"
            )
        self._consumed.add(clearance.request_id)


def issue_verified_mutation_clearance(
    *,
    request: Any,
    response: Any,
    verifier: ClearanceVerifierSeam | None,
    now: datetime,
) -> VerifiedMutationClearance:
    """Issue a mutation handle only from a fully verified ACT clearance.

    Fails closed on every gap: missing verifier, non-cleared status, missing
    or invalid Ed25519 proof, params-fingerprint or identity mismatch, missing
    or passed expiry, and observe-family capabilities.
    """

    if request is None or response is None:
        raise ProviderMutationBlockedError(
            "mutation clearance issuance requires the clearance request and response"
        )
    if verifier is None:
        raise ProviderMutationBlockedError(
            "mutation clearance issuance requires a configured ACT clearance verifier"
        )
    verification = verifier.verify(request=request, response=response, now=now)
    if not getattr(verification, "valid", False):
        reason = str(getattr(verification, "reason", "") or "clearance verification failed")
        raise ProviderMutationBlockedError(
            f"mutating transport refused clearance: {reason}"
        )
    # Belt-and-braces: even a permissive verifier cannot mint a handle without
    # a proof and expiry present on the response itself.
    if getattr(response, "proof", None) is None:
        raise ProviderMutationBlockedError(
            "mutating transport refused clearance: ACT proof is required"
        )
    expires_at = getattr(response, "expires_at", None)
    if not isinstance(expires_at, datetime) or expires_at.tzinfo is None:
        raise ProviderMutationBlockedError(
            "mutating transport refused clearance: expiry is required"
        )
    capability = str(getattr(response, "capability", "") or "")
    if capability.startswith(_REFUSED_CAPABILITY_PREFIXES) or capability in _REFUSED_CAPABILITY_IDS:
        raise ProviderMutationBlockedError(
            "mutation clearance cannot be issued for observe capabilities"
        )
    risk_family = getattr(response, "risk_family", "")
    return VerifiedMutationClearance(
        request_id=str(getattr(response, "request_id", "")),
        capability=capability,
        target=str(getattr(response, "target", "")),
        provider=str(getattr(response, "provider", "")),
        params_fingerprint=str(getattr(response, "params_fingerprint", "")),
        risk_family=str(getattr(risk_family, "value", risk_family)),
        expires_at=expires_at,
        tower_id=getattr(response, "tower_id", None),
        issued_at=now.astimezone(UTC),
        issuer=_ISSUER_TOKEN,
    )


def require_verified_mutation_clearance(
    clearance: object,
    *,
    capability: str,
    parameters: Mapping[str, Any],
    target: str,
    provider: str,
    now: datetime,
    ledger: MutationClearanceLedger,
) -> VerifiedMutationClearance:
    """Enforce every per-call mutation gate; fail closed on any mismatch.

    Checks, in order: genuine handle, capability binding, target binding,
    provider binding, params-fingerprint parity against the parameters that
    are actually about to be sent, expiry at call time, and single-use
    consumption. Refusal messages never include parameter values.
    """

    if not isinstance(clearance, VerifiedMutationClearance):
        raise ProviderMutationBlockedError(
            "mutating operations require a verified mutation clearance handle"
        )
    if clearance.capability != capability:
        raise ProviderMutationBlockedError(
            "mutation clearance capability mismatch"
        )
    if clearance.target != target:
        raise ProviderMutationBlockedError("mutation clearance target mismatch")
    if clearance.provider != provider:
        raise ProviderMutationBlockedError("mutation clearance provider mismatch")
    if fingerprint_parameters(parameters) != clearance.params_fingerprint:
        raise ProviderMutationBlockedError(
            "mutation clearance params fingerprint mismatch"
        )
    if now.astimezone(UTC) >= clearance.expires_at.astimezone(UTC):
        raise ProviderMutationBlockedError("mutation clearance expired")
    ledger.consume(clearance, now=now)
    return clearance


__all__ = [
    "ClearanceVerifierSeam",
    "MutationClearanceLedger",
    "VerifiedMutationClearance",
    "issue_verified_mutation_clearance",
    "require_verified_mutation_clearance",
]
