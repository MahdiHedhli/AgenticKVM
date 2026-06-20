"""Client-side mirror of the Agentic Control Tower clearance contract.

ACT is the source of truth for the canonical clearance request, response, and
proof format. These models mirror the published ``act.clearance.v2`` contract
(see the Tower's ``contracts/clearance/``); they are an AgenticKVM client mirror,
not an AgenticKVM-owned wire contract. Real proof verification lives in
``act_proof`` and the real transport client in ``act_http_client``.
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
CONTRACT_VERSION_V2 = "act.clearance.v2"


class ClearanceRiskFamily(StrEnum):
    """ACT-mirrored risk-family labels.

    AgenticKVM (the aircraft) only assigns the coarse ``low_risk`` / ``high_risk``
    labels -- it never derives the operator channel or tier. ACT owns risk-family
    resolution and may return one of the fine-grained ``act.clearance.v2``
    families, which are mirrored here so real tower responses parse and verify.
    """

    # Aircraft-assigned coarse labels.
    LOW_RISK = "low_risk"
    HIGH_RISK = "high_risk"
    # Tower-resolved act.clearance.v2 families (ACT owns resolution).
    OBSERVE = "observe"
    READ_ONLY = "read_only"
    ROUTINE = "routine"
    EXTERNAL_EFFECT = "external_effect"
    DESTRUCTIVE = "destructive"
    CREDENTIAL_OR_SECRET = "credential_or_secret"
    SAFETY_CRITICAL = "safety_critical"
    IRREVERSIBLE = "irreversible"


AIRCRAFT_RISK_FAMILIES = frozenset({ClearanceRiskFamily.LOW_RISK, ClearanceRiskFamily.HIGH_RISK})
TOWER_RESOLVED_RISK_FAMILIES = frozenset(
    {
        ClearanceRiskFamily.OBSERVE,
        ClearanceRiskFamily.READ_ONLY,
        ClearanceRiskFamily.ROUTINE,
        ClearanceRiskFamily.EXTERNAL_EFFECT,
        ClearanceRiskFamily.DESTRUCTIVE,
        ClearanceRiskFamily.CREDENTIAL_OR_SECRET,
        ClearanceRiskFamily.SAFETY_CRITICAL,
        ClearanceRiskFamily.IRREVERSIBLE,
    }
)

# ACT clearance state -> AgenticKVM mirror status (see the Tower contract README).
_ACT_STATE_TO_STATUS = {
    "pending": "clearance_required",
    "approved": "cleared",
    "denied": "denied",
    "expired": "expired",
    # ``cancelled`` has no AgenticKVM mirror; treat it as not-cleared (fail closed).
    "cancelled": "denied",
}


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
    contract_version: str = CONTRACT_VERSION_V2
    bound_material: Mapping[str, str] | None = None

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
        if self.bound_material is not None:
            object.__setattr__(
                self, "bound_material", MappingProxyType(dict(self.bound_material))
            )

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
            "contract_version": self.contract_version,
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


def _parse_act_datetime(value: str) -> datetime:
    text = str(value)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def clearance_response_from_act_payload(payload: Mapping[str, Any]) -> ClearanceResponse:
    """Parse a published ``act.clearance.v2`` response into the mirror model.

    Maps the ACT clearance ``state`` to the AgenticKVM mirror status, resolves
    target identity from the core field or the ``extensions.agentickvm``
    namespace, and preserves the exact wire strings ACT signed as
    ``bound_material`` so the Ed25519 proof can be verified byte-for-byte.
    """

    if not isinstance(payload, Mapping):
        raise ValueError("ACT clearance payload must be an object")

    act_state = str(payload.get("state", "")).lower()
    status_value = _ACT_STATE_TO_STATUS.get(act_state)
    status = (
        ClearanceStatus(status_value)
        if status_value is not None
        else ClearanceStatus.VERIFICATION_FAILED
    )

    request_id = str(payload.get("request_id") or payload.get("approval_id") or "")
    extensions = payload.get("extensions")
    akvm = extensions.get("agentickvm") if isinstance(extensions, Mapping) else None
    akvm = akvm if isinstance(akvm, Mapping) else {}

    target = payload.get("target") or akvm.get("target") or ""
    provider = payload.get("provider") or akvm.get("provider") or ""
    capability = payload.get("capability") or akvm.get("capability") or ""

    expires_at_raw = payload.get("expires_at")
    expires_at = _parse_act_datetime(expires_at_raw) if expires_at_raw else None

    proof = payload.get("proof")
    proof = proof if isinstance(proof, Mapping) else None
    contract_version = str(payload.get("contract_version", CONTRACT_VERSION_V2))

    bound_material = None
    if proof is not None:
        bound_material = {
            "approval_id": str(payload.get("approval_id") or request_id),
            "params_fingerprint": str(payload.get("params_fingerprint", "")),
            "short_code": str(payload.get("short_code", "")),
            "risk_family": str(payload.get("risk_family", "")),
            "expires_at": str(expires_at_raw or ""),
            "tower_id": str(payload.get("tower_id", "")),
            "contract_version": contract_version,
            "extensions_digest": str(proof.get("extensions_digest", "")),
        }

    return ClearanceResponse(
        status=status,
        request_id=request_id,
        session_id=str(payload.get("session_id") or ""),
        target=str(target),
        provider=str(provider),
        capability=str(capability),
        params_fingerprint=str(payload.get("params_fingerprint", "")),
        risk_family=str(payload.get("risk_family", "")),
        short_code=str(payload.get("short_code", "")),
        expires_at=expires_at,
        tower_id=payload.get("tower_id"),
        proof=proof,
        audit_correlation_id=str(payload.get("audit_correlation_id") or ""),
        operator_message=str(payload.get("operator_message") or ""),
        reason=str(payload.get("reason") or ""),
        contract_version=contract_version,
        bound_material=bound_material,
    )
