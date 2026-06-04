"""Host-compatible approval lifecycle models.

These models are dependency-free and JSON-safe. They model local test fixture
approval behavior for the host compatibility layer; they are not a live
operator transport.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from agentickvm.control_plane import fingerprint_parameters, redact_mapping


class HostApprovalDecision(StrEnum):
    """Operator decision represented at the host boundary."""

    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"


class HostApprovalScope(StrEnum):
    """Approval reuse scope represented at the host boundary."""

    ONE_TIME = "one_time"
    SESSION = "session"


class HostApprovalResultStatus(StrEnum):
    """Result statuses for host approval submission."""

    GRANTED = "approval_granted"
    DENIED = "approval_denied"
    EXPIRED = "approval_expired"
    VALIDATION_ERROR = "validation_error"


@dataclass(frozen=True)
class HostApprovalRequest:
    """Host-safe serialized approval request metadata."""

    id: str
    session_id: str
    target: str
    provider: str
    capability: str
    params_fingerprint: str
    expires_at: datetime
    policy_decision: str
    operator_message: str
    material_risks: tuple[str, ...] = ()
    params_preview: Mapping[str, Any] = field(default_factory=dict)
    scope_options: tuple[HostApprovalScope, ...] = (
        HostApprovalScope.ONE_TIME,
        HostApprovalScope.SESSION,
    )
    correlation_id: str | None = None
    redactions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("approval request id is required")
        if not self.session_id:
            raise ValueError("approval request session_id is required")
        if not self.target:
            raise ValueError("approval request target is required")
        if not self.provider:
            raise ValueError("approval request provider is required")
        if not self.capability:
            raise ValueError("approval request capability is required")
        if not self.params_fingerprint:
            raise ValueError("approval request params_fingerprint is required")
        safe_preview, redactions = redact_mapping(dict(self.params_preview))
        object.__setattr__(self, "params_preview", MappingProxyType(dict(safe_preview)))
        object.__setattr__(
            self,
            "redactions",
            tuple(self.redactions) + tuple(f"params_preview.{path}" for path in redactions),
        )

    @classmethod
    def from_host_result(
        cls,
        result: Mapping[str, Any],
        *,
        params: Mapping[str, Any],
        correlation_id: str | None = None,
    ) -> "HostApprovalRequest":
        """Build approval request metadata from a host/adapter result."""

        if result.get("status") != "approval_required":
            raise ValueError("host result does not require approval")
        data = _mapping(result.get("data", {}), "approval result data")
        approval = _mapping(data.get("approval_request", {}), "approval_request")
        target_scope = _mapping(approval.get("target_scope", {}), "target_scope")
        targets = target_scope.get("targets", ())
        if not isinstance(targets, list) or not targets:
            raise ValueError("approval request target scope is missing")
        capability = _mapping(approval.get("capability", {}), "capability")
        return cls(
            id=_required_str(approval, "id"),
            session_id=_required_str(approval, "session_id"),
            target=str(targets[0]),
            provider=_required_str(approval, "provider_id"),
            capability=_required_str(capability, "id"),
            params_fingerprint=_optional_str(data.get("params_fingerprint"))
            or approval_fingerprint(params),
            expires_at=_datetime_from_value(approval.get("expires_at")),
            policy_decision=_required_str(approval, "policy_decision"),
            operator_message=_required_str(approval, "operator_message"),
            material_risks=tuple(str(item) for item in approval.get("material_risks", ())),
            params_preview=_mapping(data.get("params_preview", {}), "params_preview"),
            correlation_id=correlation_id,
            redactions=tuple(str(item) for item in result.get("redactions", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe approval request dictionary."""

        return _json_safe(
            {
                "id": self.id,
                "session_id": self.session_id,
                "target": self.target,
                "provider": self.provider,
                "capability": self.capability,
                "params_fingerprint": self.params_fingerprint,
                "expires_at": self.expires_at.isoformat(),
                "policy_decision": self.policy_decision,
                "operator_message": _redact_text(self.operator_message),
                "material_risks": list(self.material_risks),
                "params_preview": dict(self.params_preview),
                "scope_options": [scope.value for scope in self.scope_options],
                "correlation_id": self.correlation_id,
                "redactions": sorted(set(self.redactions)),
            }
        )


@dataclass(frozen=True)
class HostApprovalResponse:
    """Host-safe approval response submitted by an operator or test fixture."""

    request_id: str
    decision: HostApprovalDecision
    operator_id: str
    scope: HostApprovalScope = HostApprovalScope.ONE_TIME
    reason: str | None = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    session_id: str | None = None
    target: str | None = None
    provider: str | None = None
    capability: str | None = None
    params_fingerprint: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id:
            raise ValueError("approval response request_id is required")
        if not self.operator_id:
            raise ValueError("approval response operator_id is required")
        object.__setattr__(self, "reason", _redact_text(self.reason or ""))

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "HostApprovalResponse":
        """Build a response from a JSON-like mapping."""

        return cls(
            request_id=_required_str(values, "request_id"),
            decision=HostApprovalDecision(_required_str(values, "decision")),
            operator_id=_required_str(values, "operator_id"),
            scope=HostApprovalScope(str(values.get("scope", HostApprovalScope.ONE_TIME.value))),
            reason=_optional_str(values.get("reason")),
            decided_at=_datetime_from_value(values.get("decided_at")),
            session_id=_optional_str(values.get("session_id")),
            target=_optional_str(values.get("target")),
            provider=_optional_str(values.get("provider")),
            capability=_optional_str(values.get("capability")),
            params_fingerprint=_optional_str(values.get("params_fingerprint")),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe approval response dictionary."""

        return _json_safe(
            {
                "request_id": self.request_id,
                "decision": self.decision.value,
                "operator_id": self.operator_id,
                "scope": self.scope.value,
                "reason": self.reason,
                "decided_at": self.decided_at.isoformat(),
                "session_id": self.session_id,
                "target": self.target,
                "provider": self.provider,
                "capability": self.capability,
                "params_fingerprint": self.params_fingerprint,
            }
        )


@dataclass(frozen=True)
class HostApprovalResult:
    """Host-safe result for approval response submission."""

    status: HostApprovalResultStatus
    request_id: str
    reason: str
    approval_request: HostApprovalRequest | None = None
    response: HostApprovalResponse | None = None
    grant: Mapping[str, Any] = field(default_factory=dict)
    redactions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        safe_grant, redactions = redact_mapping(dict(self.grant))
        object.__setattr__(self, "reason", _redact_text(self.reason))
        object.__setattr__(self, "grant", MappingProxyType(dict(safe_grant)))
        object.__setattr__(
            self,
            "redactions",
            tuple(self.redactions) + tuple(f"grant.{path}" for path in redactions),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe approval result dictionary."""

        payload: dict[str, Any] = {
            "status": self.status.value,
            "request_id": self.request_id,
            "reason": self.reason,
            "grant": dict(self.grant),
            "redactions": sorted(set(self.redactions)),
        }
        if self.approval_request is not None:
            payload["approval_request"] = self.approval_request.to_dict()
        if self.response is not None:
            payload["response"] = self.response.to_dict()
        return _json_safe(payload)


def approval_fingerprint(parameters: Mapping[str, Any]) -> str:
    """Return the stable host action fingerprint for safe parameters."""

    return fingerprint_parameters(parameters)


def _required_str(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"approval {key} is required")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("approval optional string fields must be strings")
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return value


def _datetime_from_value(value: Any) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        raise ValueError("approval datetime fields must be ISO datetime strings")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _redact_text(value: str) -> str:
    lowered = value.lower()
    if any(
        fragment in lowered
        for fragment in (
            "password",
            "secret",
            "token",
            "api_key",
            "private_key",
            "credential",
            "bearer",
            "session_cookie",
            "cookie",
        )
    ):
        return "[REDACTED]"
    return value


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


__all__ = [
    "HostApprovalDecision",
    "HostApprovalRequest",
    "HostApprovalResponse",
    "HostApprovalResult",
    "HostApprovalResultStatus",
    "HostApprovalScope",
    "approval_fingerprint",
]
