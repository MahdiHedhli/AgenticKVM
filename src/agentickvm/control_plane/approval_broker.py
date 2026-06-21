"""Approval Broker v1 signing and verification primitives."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Mapping, Protocol
from uuid import uuid4

if TYPE_CHECKING:
    from agentickvm.control_plane.signer_trust import SignerTrustRegistry

from agentickvm.control_plane.approvals import APPROVAL_RESUMPTION_BLOCKED_CAPABILITIES
from agentickvm.control_plane.fingerprints import fingerprint_parameters
from agentickvm.control_plane.grants import (
    ApprovalChannel,
    ApprovalRiskSummary,
    ApprovalShortCode,
    GrantPayload,
    GrantVerificationResult,
    GrantVerificationStatus,
    SignedApprovalGrant,
)


DEFAULT_APPROVAL_TIMEOUT_SECONDS = 20


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


@dataclass(frozen=True)
class BrokerApprovalRequest:
    """Broker-owned approval request metadata."""

    request_id: str
    session_id: str
    target: str
    provider: str
    capability: str
    params_fingerprint: str
    risk_summary: ApprovalRiskSummary
    channel: ApprovalChannel
    short_code: ApprovalShortCode
    operator_message: str
    retry_instructions: str
    created_at: datetime
    expires_at: datetime
    timeout_seconds: int = DEFAULT_APPROVAL_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if self.timeout_seconds > DEFAULT_APPROVAL_TIMEOUT_SECONDS:
            raise ValueError("approval timeout cannot exceed default maximum without explicit policy")
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("approval timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("approval request expiry must be after creation")
        if ".." in self.operator_message:
            raise ValueError("operator message must not contain double periods")

    def to_approval_required(self) -> dict[str, Any]:
        """Return JSON-safe approval_required data."""

        return {
            "status": "approval_required",
            "approval_request": {
                "id": self.request_id,
                "session_id": self.session_id,
                "target": self.target,
                "provider": self.provider,
                "capability": self.capability,
                "params_fingerprint": self.params_fingerprint,
                "risk_family": self.risk_summary.risk_family,
                "channel": self.channel.value,
                "short_code": self.short_code.value,
                "operator_message": self.operator_message,
                "risk_summary": self.risk_summary.to_dict(),
                "retry_instructions": self.retry_instructions,
                "created_at": self.created_at.astimezone(UTC).isoformat(),
                "expires_at": self.expires_at.astimezone(UTC).isoformat(),
                "timeout_seconds": self.timeout_seconds,
            },
        }


class ApprovalBroker:
    """Create approval requests and operator-facing messages."""

    def __init__(
        self,
        *,
        timeout_seconds: int = DEFAULT_APPROVAL_TIMEOUT_SECONDS,
        id_factory: Any | None = None,
    ) -> None:
        if timeout_seconds < 0:
            raise ValueError("approval timeout cannot be negative")
        if timeout_seconds > DEFAULT_APPROVAL_TIMEOUT_SECONDS:
            raise ValueError("approval timeout cannot exceed default maximum without explicit policy")
        self.timeout_seconds = timeout_seconds
        self.id_factory = id_factory or (lambda: uuid4().hex)

    def request_approval(
        self,
        *,
        session_id: str,
        target: str,
        provider: str,
        capability: str,
        parameters: Mapping[str, object],
        risk_family: str,
        risk_summary: str,
        material_risks: tuple[str, ...],
        intended_effect: str,
        now: datetime,
        expires_at: datetime,
        channel: ApprovalChannel = ApprovalChannel.OUT_OF_BAND,
    ) -> BrokerApprovalRequest:
        """Create a broker-owned approval request without blocking."""

        request_id = str(self.id_factory())
        params_fingerprint = fingerprint_parameters(parameters)
        short_code = ApprovalShortCode(_short_code(request_id, params_fingerprint))
        risk = ApprovalRiskSummary(
            risk_family=risk_family,
            summary=risk_summary,
            material_risks=material_risks,
        )
        message = _operator_message(
            short_code=short_code.value,
            capability=capability,
            target=target,
            provider=provider,
            intended_effect=intended_effect,
            risk_summary=risk_summary,
        )
        return BrokerApprovalRequest(
            request_id=request_id,
            session_id=session_id,
            target=target,
            provider=provider,
            capability=capability,
            params_fingerprint=params_fingerprint,
            risk_summary=risk,
            channel=channel,
            short_code=short_code,
            operator_message=message,
            retry_instructions=(
                "After operator approval, re-call the same tool with identical "
                "target, provider, capability, and parameters."
            ),
            created_at=now.astimezone(UTC),
            expires_at=expires_at.astimezone(UTC),
            timeout_seconds=self.timeout_seconds,
        )


class ApprovalGrantVerifier:
    """Verify signed grants against trusted signers and exact request context."""

    def __init__(self, signers: Mapping[str, ApprovalSigner]) -> None:
        self.signers = dict(signers)

    @classmethod
    def from_trust_registry(cls, registry: "SignerTrustRegistry") -> "ApprovalGrantVerifier":
        """Build a verifier that accepts only the registry's trusted signers.

        Untrusted or development signers are excluded, so a grant signed by them
        fails closed with ``untrusted signer key id``.
        """

        return cls(signers=registry.trusted_signers())

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


def _short_code(request_id: str, params_fingerprint: str) -> str:
    digest = hashlib.sha256(f"{request_id}:{params_fingerprint}".encode("utf-8")).hexdigest()
    raw = digest[:8].upper()
    return f"{raw[:4]}-{raw[4:]}"


def _operator_message(
    *,
    short_code: str,
    capability: str,
    target: str,
    provider: str,
    intended_effect: str,
    risk_summary: str,
) -> str:
    message = (
        f"Approval {short_code} required for {capability} on target {target} "
        f"through provider {provider}. Intended effect: {intended_effect}. "
        f"Risk: {risk_summary}. Surface this code to the operator and retry "
        "with identical parameters after approval."
    )
    while ".." in message:
        message = message.replace("..", ".")
    return message
