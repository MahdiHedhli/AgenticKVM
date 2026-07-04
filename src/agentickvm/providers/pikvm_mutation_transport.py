"""PiKVM ATX live MUTATION transport boundary.

The separate explicit mutating path next to the observe-only
``pikvm_transport`` seam. Socket-free by injection: the TLS probe and the
POST-capable client are injected; the only real network implementations live
in ``agentickvm.live_validation`` for operator-run sessions.

Every mutating verb requires, fail-closed: a pinned certificate fingerprint,
a passed TLS pin preflight, and a single-use ``VerifiedMutationClearance``
handle bound to this capability, target, provider, and params fingerprint.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any, Callable, Protocol

from agentickvm.providers.errors import (
    ProviderMutationBlockedError,
    ProviderProtocolError,
)
from agentickvm.providers.mutation_gate import (
    MutationClearanceLedger,
    VerifiedMutationClearance,
    require_verified_mutation_clearance,
)
from agentickvm.providers.pikvm_transport import (
    PIKVM_ATX_POWER_CYCLE_PATH,
    PIKVM_ATX_POWER_OFF_PATH,
    PIKVM_ATX_POWER_ON_PATH,
    PiKVMCredentialRef,
    PiKVMFingerprintMismatchError,
    PiKVMPinnedTrust,
    PiKVMTargetConfig,
    PiKVMTLSProbe,
    normalize_cert_fingerprint,
    redact_pikvm_observe_payload,
)
from agentickvm.providers.transport_policy import TransportSecurityPolicy
from agentickvm.providers.transports import TransportError

# The only mutating verbs this transport implements. HID input, MSD, and ATX
# reset remain unimplemented and unreachable through the live layer.
PIKVM_LIVE_MUTATING_OPERATIONS = frozenset(
    {
        "power.on",
        "power.force_off",
        "power.power_cycle",
    }
)

_PIKVM_ATX_PATHS = {
    "power.on": PIKVM_ATX_POWER_ON_PATH,
    "power.force_off": PIKVM_ATX_POWER_OFF_PATH,
    "power.power_cycle": PIKVM_ATX_POWER_CYCLE_PATH,
}


class PiKVMHTTPMutationClient(Protocol):
    """POST-capable client built per actuation after every gate passes."""

    trust: PiKVMPinnedTrust

    def post_json(
        self, path: str, body: Mapping[str, Any], *, timeout_seconds: float
    ) -> Mapping[str, Any]:
        """Perform a mutating POST and return the JSON response object."""


PiKVMMutationHTTPClientFactory = Callable[
    [
        PiKVMTargetConfig,
        PiKVMCredentialRef,
        PiKVMPinnedTrust,
        VerifiedMutationClearance,
    ],
    PiKVMHTTPMutationClient,
]


class LivePiKVMMutationTransport:
    """Clearance-gated PiKVM ATX mutation transport built after pin preflight.

    The mutating HTTP client is built per actuation call, only after the
    per-call clearance gates pass, so credentials are never resolved for a
    refused mutation.
    """

    def __init__(
        self,
        *,
        config: PiKVMTargetConfig,
        credential_ref: PiKVMCredentialRef,
        target_id: str,
        provider_id: str,
        tls_probe: PiKVMTLSProbe,
        http_client_factory: PiKVMMutationHTTPClientFactory,
        ledger: MutationClearanceLedger | None = None,
        policy: TransportSecurityPolicy | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        if not config.cert_fingerprint:
            raise ProviderMutationBlockedError(
                "mutating PiKVM transport requires a pinned certificate "
                "fingerprint; no pin means no mutation"
            )
        if not target_id or not provider_id:
            raise ProviderMutationBlockedError(
                "mutating PiKVM transport requires target and provider identity"
            )
        self.config = config
        self.credential_ref = credential_ref
        self.target_id = target_id
        self.provider_id = provider_id
        self.policy = policy or TransportSecurityPolicy(
            read_timeout_seconds=config.read_timeout_seconds,
            connect_timeout_seconds=config.connect_timeout_seconds,
            tls_verify=config.verify_ssl,
            allow_insecure_tls=not config.verify_ssl and bool(config.cert_fingerprint),
        )
        self._ledger = ledger or MutationClearanceLedger()
        self._now_factory = now_factory or (lambda: datetime.now(UTC))
        self._http_client_factory = http_client_factory
        self._trust = self._preflight_pin(tls_probe)

    # -- mutating verbs ------------------------------------------------------

    def power_on(self, *, clearance: object) -> Mapping[str, Any]:
        """ATX power on (clearance-gated)."""

        return self._atx("power.on", clearance)

    def power_force_off(self, *, clearance: object) -> Mapping[str, Any]:
        """ATX hard power off (clearance-gated)."""

        return self._atx("power.force_off", clearance)

    def power_cycle(self, *, clearance: object) -> Mapping[str, Any]:
        """ATX power cycle (clearance-gated)."""

        return self._atx("power.power_cycle", clearance)

    # -- internals -----------------------------------------------------------

    def _atx(self, capability: str, clearance: object) -> Mapping[str, Any]:
        if capability not in PIKVM_LIVE_MUTATING_OPERATIONS:
            raise ProviderMutationBlockedError(
                "PiKVM live mutation transport does not implement this verb"
            )
        verified = require_verified_mutation_clearance(
            clearance,
            capability=capability,
            parameters={},
            target=self.target_id,
            provider=self.provider_id,
            now=self._now_factory(),
            ledger=self._ledger,
        )
        client = self._http_client_factory(
            self.config, self.credential_ref, self._trust, verified
        )
        try:
            payload = client.post_json(
                _PIKVM_ATX_PATHS[capability],
                {},
                timeout_seconds=self.policy.read_timeout_seconds,
            )
        except TransportError as exc:
            raise ProviderProtocolError("PiKVM live mutation transport error") from exc
        return MappingProxyType(
            {
                "capability": capability,
                "performed": True,
                "response": redact_pikvm_observe_payload(dict(payload)),
            }
        )

    def _preflight_pin(self, tls_probe: PiKVMTLSProbe) -> PiKVMPinnedTrust:
        expected = normalize_cert_fingerprint(self.config.cert_fingerprint)
        observed = normalize_cert_fingerprint(
            tls_probe.certificate_der_sha256(
                host=self.config.host,
                port=self.config.port,
                timeout_seconds=self.config.connect_timeout_seconds,
            )
        )
        if observed != expected:
            raise PiKVMFingerprintMismatchError(
                "PiKVM certificate fingerprint mismatch; credentials were not sent"
            )
        return PiKVMPinnedTrust(expected)


__all__ = [
    "LivePiKVMMutationTransport",
    "PIKVM_LIVE_MUTATING_OPERATIONS",
    "PiKVMHTTPMutationClient",
    "PiKVMMutationHTTPClientFactory",
]
