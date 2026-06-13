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

    risk_family: str
    summary: str
    material_risks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.risk_family:
            raise ValueError("risk family is required")
        if not self.summary:
            raise ValueError("risk summary is required")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dictionary."""

        return {
            "risk_family": self.risk_family,
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
    params_fingerprint: str
    risk_summary: ClearanceRiskSummary
    operator_message: str
    requested_by: str
    created_at: datetime
    expires_at: datetime
    short_code: str
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
        if self.created_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("clearance timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("clearance expiry must be after creation")
        if ".." in self.operator_message:
            raise ValueError("operator message must not contain double periods")
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
            "risk_family": self.risk_summary.risk_family,
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
    params_fingerprint: str
    expires_at: datetime | None = None
    tower_id: str | None = None
    proof: Mapping[str, Any] | None = None
    audit_correlation_id: str = ""
    operator_message: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("clearance response expiry must be timezone-aware")
        if self.operator_message and ".." in self.operator_message:
            raise ValueError("operator message must not contain double periods")
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
    risk_family: str,
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
    params_fingerprint = fingerprint_parameters(parameters)
    short_code = _short_code(request_id, params_fingerprint)
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
