"""Approval Broker v1 signing and verification primitives."""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Mapping, Protocol

from agentickvm.control_plane.approvals import APPROVAL_RESUMPTION_BLOCKED_CAPABILITIES
from agentickvm.control_plane.fingerprints import fingerprint_parameters
from agentickvm.control_plane.grants import (
    ApprovalChannel,
    GrantPayload,
    GrantVerificationResult,
    GrantVerificationStatus,
    SignedApprovalGrant,
)


BANNED_CONVERSATIONAL_RISK_FAMILIES = frozenset(
    {
        "power",
        "input",
        "boot",
        "media",
        "provider_mutation",
        "credentials",
        "policy",
        "audit",
        "emergency_stop",
    }
)


class ApprovalSigner(Protocol):
    """Signer interface for broker-owned grants."""

    key_id: str
    signature_algorithm: str

    def sign(self, payload: GrantPayload) -> SignedApprovalGrant:
        """Return a signed grant."""

    def verify(self, signed_grant: SignedApprovalGrant) -> bool:
        """Return whether a signed grant verifies for this signer."""


@dataclass(frozen=True)
class HMACDevelopmentSigner:
    """Development/test HMAC signer.

    This signer is safe for tests and local development only. It is not a
    production authority when the agent can read the key.
    """

    key_id: str
    secret: bytes
    signature_algorithm: str = "hmac-sha256"

    def __post_init__(self) -> None:
        if not self.key_id:
            raise ValueError("signer key id is required")
        if not self.secret:
            raise ValueError("development signer secret is required")

    def sign(self, payload: GrantPayload) -> SignedApprovalGrant:
        """Return a signed grant."""

        if payload.signer_key_id != self.key_id:
            raise ValueError("payload signer key id does not match signer")
        return SignedApprovalGrant(
            payload=payload,
            signature=self._signature_for(payload),
            signature_algorithm=self.signature_algorithm,
        )

    def verify(self, signed_grant: SignedApprovalGrant) -> bool:
        """Return whether the signed grant matches this signer."""

        if signed_grant.signature_algorithm != self.signature_algorithm:
            return False
        if signed_grant.payload.signer_key_id != self.key_id:
            return False
        expected = self._signature_for(signed_grant.payload)
        return hmac.compare_digest(expected, signed_grant.signature)

    def _signature_for(self, payload: GrantPayload) -> str:
        message = payload.canonical_payload().encode("utf-8")
        return hmac.new(self.secret, message, sha256).hexdigest()


@dataclass(frozen=True)
class GrantVerificationContext:
    """Expected binding for a signed grant verification."""

    request_id: str
    session_id: str
    target: str
    provider: str
    capability: str
    params_fingerprint: str
    risk_family: str
    now: datetime
    allowed_conversational_risk_families: frozenset[str] = field(
        default_factory=lambda: frozenset({"observe", "runtime"})
    )

    @classmethod
    def from_parameters(
        cls,
        *,
        request_id: str,
        session_id: str,
        target: str,
        provider: str,
        capability: str,
        parameters: Mapping[str, object],
        risk_family: str,
        now: datetime,
    ) -> "GrantVerificationContext":
        """Build a verification context from request parameters."""

        return cls(
            request_id=request_id,
            session_id=session_id,
            target=target,
            provider=provider,
            capability=capability,
            params_fingerprint=fingerprint_parameters(parameters),
            risk_family=risk_family,
            now=now,
        )


class ApprovalGrantVerifier:
    """Verify signed grants against trusted signers and exact request context."""

    def __init__(self, signers: Mapping[str, ApprovalSigner]) -> None:
        self.signers = dict(signers)

    def verify(
        self,
        signed_grant: SignedApprovalGrant | None,
        *,
        context: GrantVerificationContext,
    ) -> GrantVerificationResult:
        """Verify a signed grant for the expected request context."""

        if signed_grant is None:
            return GrantVerificationResult(
                status=GrantVerificationStatus.UNSIGNED,
                reason="signed grant is required",
                request_id=context.request_id,
            )

        payload = signed_grant.payload
        base = {
            "request_id": payload.request_id,
            "grant_id": payload.grant_id,
            "signer_key_id": payload.signer_key_id,
        }
        signer = self.signers.get(payload.signer_key_id)
        if signer is None:
            return GrantVerificationResult(
                status=GrantVerificationStatus.REJECTED,
                reason="untrusted signer key id",
                **base,
            )
        if not signer.verify(signed_grant):
            return GrantVerificationResult(
                status=GrantVerificationStatus.REJECTED,
                reason="invalid signature",
                **base,
            )
        mismatch = _first_mismatch(
            {
                "request_id": (payload.request_id, context.request_id),
                "session_id": (payload.session_id, context.session_id),
                "target": (payload.target, context.target),
                "provider": (payload.provider, context.provider),
                "capability": (payload.capability, context.capability),
                "params_fingerprint": (
                    payload.params_fingerprint,
                    context.params_fingerprint,
                ),
                "risk_family": (payload.risk_family, context.risk_family),
            }
        )
        if mismatch is not None:
            return GrantVerificationResult(
                status=GrantVerificationStatus.REJECTED,
                reason=f"{mismatch} mismatch",
                **base,
            )
        if payload.capability in APPROVAL_RESUMPTION_BLOCKED_CAPABILITIES:
            return GrantVerificationResult(
                status=GrantVerificationStatus.REJECTED,
                reason="hard invariant capability cannot be approved",
                **base,
            )
        if context.now >= payload.expires_at:
            return GrantVerificationResult(
                status=GrantVerificationStatus.EXPIRED,
                reason="grant expired",
                **base,
            )
        if payload.one_time and payload.consumed_at is not None:
            return GrantVerificationResult(
                status=GrantVerificationStatus.CONSUMED,
                reason="one-time grant already consumed",
                **base,
            )
        if payload.channel == ApprovalChannel.CONVERSATIONAL:
            if payload.risk_family in BANNED_CONVERSATIONAL_RISK_FAMILIES:
                return GrantVerificationResult(
                    status=GrantVerificationStatus.REJECTED,
                    reason="conversational approval banned for risk family",
                    **base,
                )
            if payload.risk_family not in context.allowed_conversational_risk_families:
                return GrantVerificationResult(
                    status=GrantVerificationStatus.REJECTED,
                    reason="conversational approval not allowed for risk family",
                    **base,
                )
        return GrantVerificationResult(
            status=GrantVerificationStatus.VALID,
            reason="grant verified",
            **base,
        )


def build_grant_payload(
    *,
    grant_id: str,
    request_id: str,
    session_id: str,
    target: str,
    provider: str,
    capability: str,
    parameters: Mapping[str, object],
    risk_family: str,
    channel: ApprovalChannel,
    expires_at: datetime,
    signer_key_id: str,
    one_time: bool = True,
) -> GrantPayload:
    """Build a grant payload with a stable parameter fingerprint."""

    return GrantPayload(
        grant_id=grant_id,
        request_id=request_id,
        session_id=session_id,
        target=target,
        provider=provider,
        capability=capability,
        params_fingerprint=fingerprint_parameters(parameters),
        risk_family=risk_family,
        channel=channel,
        expires_at=expires_at.astimezone(UTC),
        one_time=one_time,
        signer_key_id=signer_key_id,
    )


def _first_mismatch(values: Mapping[str, tuple[str, str]]) -> str | None:
    for field_name, (actual, expected) in values.items():
        if actual != expected:
            return field_name
    return None
