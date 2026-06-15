"""Client-side mirror of the Agentic Control Tower clearance contract.

ACT is the source of truth for the canonical clearance request, response, and
proof format. These models are AgenticKVM client mirrors pending alignment with
the canonical ACT spec; they are not an AgenticKVM-owned wire contract.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from agentickvm.control_plane.fingerprints import fingerprint_parameters


ACT_AIRCRAFT_ID = "AgenticKVM"
DEFAULT_CLEARANCE_TIMEOUT_SECONDS = 20


class ClearanceRiskFamily(StrEnum):
    """ACT-mirrored risk-family labels assigned by the AgenticKVM aircraft."""

    LOW_RISK = "low_risk"
    HIGH_RISK = "high_risk"


class ClearanceParamsFingerprint(str):
    """Typed ACT-mirrored params fingerprint."""

    def __new__(cls, value: str) -> "ClearanceParamsFingerprint":
        if not value:
            raise ValueError("clearance params_fingerprint is required")
        return str.__new__(cls, value)


class ClearanceShortCode(str):
    """Typed ACT-mirrored operator short code."""

    def __new__(cls, value: str) -> "ClearanceShortCode":
        if not value:
            raise ValueError("clearance short_code is required")
        return str.__new__(cls, value)


class ClearanceOperatorMessage(str):
    """Typed ACT-mirrored operator message."""

    def __new__(cls, value: str) -> "ClearanceOperatorMessage":
        if not value:
            raise ValueError("clearance operator_message is required")
        if ".." in value:
            raise ValueError("operator message must not contain double periods")
        return str.__new__(cls, value)


class ClearanceStatus(StrEnum):
    """ACT clearance response states mirrored by the AgenticKVM client."""

    CLEARANCE_REQUIRED = "clearance_required"
    CLEARED = "cleared"
    DENIED = "denied"
    EXPIRED = "expired"
    INVALID = "invalid"
    TOWER_UNAVAILABLE = "tower_unavailable"
    VERIFICATION_FAILED = "verification_failed"


@dataclass(frozen=True)
class ClearanceRiskSummary:
    """Operator-readable risk summary mirrored for ACT clearance requests."""

    risk_family: ClearanceRiskFamily | str
    summary: str
    material_risks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_family", _risk_family(self.risk_family))
        if not self.summary:
            raise ValueError("risk summary is required")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dictionary."""

        return {
            "risk_family": self.risk_family.value,
            "summary": self.summary,
            "material_risks": list(self.material_risks),
        }


@dataclass(frozen=True)
class ClearanceRequest:
    """AgenticKVM client-side mirror of an ACT clearance request."""

    request_id: str
    session_id: str
    target: str
    provider: str
    capability: str
    params_fingerprint: ClearanceParamsFingerprint | str
    risk_summary: ClearanceRiskSummary
    operator_message: ClearanceOperatorMessage | str
    requested_by: str
    created_at: datetime
    expires_at: datetime
    short_code: ClearanceShortCode | str
    policy_context: Mapping[str, Any] = field(default_factory=dict)
    audit_correlation_id: str = ""
    aircraft: str = ACT_AIRCRAFT_ID

    def __post_init__(self) -> None:
        required = {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "target": self.target,
            "provider": self.provider,
            "capability": self.capability,
            "params_fingerprint": self.params_fingerprint,
            "operator_message": self.operator_message,
            "requested_by": self.requested_by,
            "short_code": self.short_code,
            "audit_correlation_id": self.audit_correlation_id,
            "aircraft": self.aircraft,
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"clearance request missing required fields: {', '.join(missing)}")
        object.__setattr__(
            self,
            "params_fingerprint",
            ClearanceParamsFingerprint(str(self.params_fingerprint)),
        )
        object.__setattr__(
            self,
            "operator_message",
            ClearanceOperatorMessage(str(self.operator_message)),
        )
        object.__setattr__(self, "short_code", ClearanceShortCode(str(self.short_code)))
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("clearance timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("clearance expiry must be after creation")
        object.__setattr__(self, "policy_context", MappingProxyType(dict(self.policy_context)))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe ACT clearance request mirror."""

        return {
            "aircraft": self.aircraft,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "target": self.target,
            "provider": self.provider,
            "capability": self.capability,
            "params_fingerprint": self.params_fingerprint,
            "risk_family": self.risk_summary.risk_family.value,
            "risk_summary": self.risk_summary.to_dict(),
            "operator_message": self.operator_message,
            "requested_by": self.requested_by,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "expires_at": self.expires_at.astimezone(UTC).isoformat(),
            "short_code": self.short_code,
            "policy_context": dict(self.policy_context),
            "audit_correlation_id": self.audit_correlation_id,
        }


@dataclass(frozen=True)
class ClearanceResponse:
    """AgenticKVM client-side mirror of an ACT clearance response."""

    status: ClearanceStatus
    request_id: str
    session_id: str
    target: str
    provider: str
    capability: str
    params_fingerprint: ClearanceParamsFingerprint | str
    risk_family: ClearanceRiskFamily | str
    short_code: ClearanceShortCode | str
    expires_at: datetime | None = None
    tower_id: str | None = None
    proof: Mapping[str, Any] | None = None
    audit_correlation_id: str = ""
    operator_message: ClearanceOperatorMessage | str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "params_fingerprint",
            ClearanceParamsFingerprint(str(self.params_fingerprint)),
        )
        object.__setattr__(self, "risk_family", _risk_family(self.risk_family))
        object.__setattr__(self, "short_code", ClearanceShortCode(str(self.short_code)))
        if self.operator_message:
            object.__setattr__(
                self,
                "operator_message",
                ClearanceOperatorMessage(str(self.operator_message)),
            )
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("clearance response expiry must be timezone-aware")
        if self.proof is not None:
            object.__setattr__(self, "proof", MappingProxyType(dict(self.proof)))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe ACT clearance response mirror."""

        return {
            "status": self.status.value,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "target": self.target,
            "provider": self.provider,
            "capability": self.capability,
            "params_fingerprint": self.params_fingerprint,
            "risk_family": self.risk_family.value,
            "short_code": self.short_code,
            "expires_at": self.expires_at.astimezone(UTC).isoformat()
            if self.expires_at
            else None,
            "tower_id": self.tower_id,
            "proof": dict(self.proof) if self.proof is not None else None,
            "audit_correlation_id": self.audit_correlation_id,
            "operator_message": self.operator_message,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ClearanceVerificationResult:
    """Result of verifying an ACT clearance response as a client."""

    valid: bool
    status: ClearanceStatus
    reason: str
    tower_id: str | None = None
    request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe verification result."""

        return {
            "valid": self.valid,
            "status": self.status.value,
            "reason": self.reason,
            "tower_id": self.tower_id,
            "request_id": self.request_id,
        }


def build_clearance_request(
    *,
    session_id: str,
    target: str,
    provider: str,
    capability: str,
    parameters: Mapping[str, object],
    risk_family: ClearanceRiskFamily | str,
    risk_summary: str,
    material_risks: tuple[str, ...],
    intended_effect: str,
    requested_by: str,
    audit_correlation_id: str,
    policy_context: Mapping[str, Any],
    now: datetime,
    ttl_seconds: int = DEFAULT_CLEARANCE_TIMEOUT_SECONDS,
    request_id: str | None = None,
) -> ClearanceRequest:
    """Build an ACT clearance request mirror with stable fingerprint and code."""

    if ttl_seconds < 0:
        raise ValueError("clearance ttl cannot be negative")
    if ttl_seconds > DEFAULT_CLEARANCE_TIMEOUT_SECONDS:
        raise ValueError("clearance ttl cannot exceed default without explicit policy")
    request_id = request_id or uuid4().hex
    params_fingerprint = ClearanceParamsFingerprint(fingerprint_parameters(parameters))
    short_code = ClearanceShortCode(_short_code(request_id, params_fingerprint))
    risk = ClearanceRiskSummary(
        risk_family=risk_family,
        summary=risk_summary,
        material_risks=material_risks,
    )
    operator_message = build_operator_message(
        short_code=short_code,
        capability=capability,
        target=target,
        provider=provider,
        intended_effect=intended_effect,
        risk_summary=risk_summary,
    )
    return ClearanceRequest(
        request_id=request_id,
        session_id=session_id,
        target=target,
        provider=provider,
        capability=capability,
        params_fingerprint=params_fingerprint,
        risk_summary=risk,
        operator_message=operator_message,
        requested_by=requested_by,
        created_at=now.astimezone(UTC),
        expires_at=now.astimezone(UTC) + timedelta(seconds=ttl_seconds),
        short_code=short_code,
        policy_context=policy_context,
        audit_correlation_id=audit_correlation_id,
    )


def build_operator_message(
    *,
    short_code: str,
    capability: str,
    target: str,
    provider: str,
    intended_effect: str,
    risk_summary: str,
) -> str:
    """Build the chat-rendered operator message for ACT clearance."""

    message = (
        f"Clearance {short_code} required for {capability} on target {target} "
        f"through provider {provider}. Intended effect: {intended_effect}. "
        f"Risk: {risk_summary}. Surface this code to the operator and retry "
        "with identical parameters after approval."
    )
    while ".." in message:
        message = message.replace("..", ".")
    return message


def _short_code(request_id: str, params_fingerprint: str) -> str:
    digest = hashlib.sha256(f"{request_id}:{params_fingerprint}".encode("utf-8")).hexdigest()
    raw = digest[:8].upper()
    return f"{raw[:4]}-{raw[4:]}"


def _risk_family(value: ClearanceRiskFamily | str) -> ClearanceRiskFamily:
    if isinstance(value, ClearanceRiskFamily):
        return value
    if not value:
        raise ValueError("clearance risk_family is required")
    try:
        return ClearanceRiskFamily(str(value))
    except ValueError as exc:
        raise ValueError(f"unknown clearance risk_family: {value}") from exc
