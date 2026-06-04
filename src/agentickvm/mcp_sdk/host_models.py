"""Dependency-free MCP host compatibility models.

These models are local and JSON-safe. They are not a live MCP SDK protocol
implementation and they do not perform provider execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from agentickvm.control_plane import redact_mapping


class HostResultStatus(StrEnum):
    """Result statuses exposed by the host compatibility layer."""

    OK = "ok"
    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"
    VALIDATION_ERROR = "validation_error"
    PROVIDER_ERROR = "provider_error"
    POLICY_ERROR = "policy_error"


HOST_RESULT_STATUSES: tuple[str, ...] = tuple(status.value for status in HostResultStatus)


@dataclass(frozen=True)
class HostToolDescriptor:
    """JSON-safe descriptor returned by host tool listing."""

    tool_name: str
    capability: str
    description: str
    dangerous: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe descriptor dictionary."""

        return _json_safe(
            {
                "tool_name": self.tool_name,
                "capability": self.capability,
                "description": self.description,
                "dangerous": self.dangerous,
            }
        )


@dataclass(frozen=True)
class HostToolSchema:
    """JSON-safe schema returned to a future MCP host."""

    tool_name: str
    capability: str
    description: str
    dangerous: bool
    input_schema: Mapping[str, Any]
    possible_statuses: tuple[str, ...] = HOST_RESULT_STATUSES

    def __post_init__(self) -> None:
        safe_schema, _ = redact_mapping(dict(self.input_schema))
        object.__setattr__(self, "input_schema", MappingProxyType(dict(safe_schema)))

    @classmethod
    def from_adapter_schema(cls, payload: Mapping[str, Any]) -> "HostToolSchema":
        """Build a host schema from an SDK adapter schema payload."""

        if payload.get("status") != HostResultStatus.OK.value:
            raise ValueError(str(payload.get("reason", "tool schema unavailable")))
        capability = payload.get("capability")
        description = payload.get("description")
        tool_name = payload.get("tool_name")
        input_schema = payload.get("input")
        if not isinstance(tool_name, str) or not tool_name:
            raise ValueError("tool schema missing tool_name")
        if not isinstance(capability, str) or not capability:
            raise ValueError("tool schema missing capability")
        if not isinstance(description, str):
            raise ValueError("tool schema missing description")
        if not isinstance(input_schema, Mapping):
            raise ValueError("tool schema missing input")
        return cls(
            tool_name=tool_name,
            capability=capability,
            description=description,
            dangerous=bool(payload.get("dangerous", False)),
            input_schema=input_schema,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe schema dictionary."""

        return _json_safe(
            {
                "status": HostResultStatus.OK.value,
                "tool_name": self.tool_name,
                "capability": self.capability,
                "description": self.description,
                "dangerous": self.dangerous,
                "input": dict(self.input_schema),
                "possible_statuses": list(self.possible_statuses),
            }
        )


@dataclass(frozen=True)
class HostToolCall:
    """Tool call accepted by the host compatibility layer."""

    tool_name: str
    target: str
    session_id: str = "host-session"
    requester_id: str = "mcp-host"
    params: Mapping[str, Any] = field(default_factory=dict)
    provider: str | None = None
    requested_mode: str | None = None
    policy_ref: str | None = None
    approval_context: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.tool_name:
            raise ValueError("host tool_name is required")
        if not self.target:
            raise ValueError("host target is required")
        if not self.session_id:
            raise ValueError("host session_id is required")
        if not self.requester_id:
            raise ValueError("host requester_id is required")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        object.__setattr__(
            self,
            "approval_context",
            MappingProxyType(dict(self.approval_context)),
        )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "HostToolCall":
        """Build a host call from a JSON-like mapping."""

        return cls(
            tool_name=_required_str(values, "tool_name"),
            target=_required_str(values, "target"),
            session_id=str(values.get("session_id", "host-session")),
            requester_id=str(values.get("requester_id", "mcp-host")),
            params=_mapping(values.get("params", {}), "params"),
            provider=_optional_str(values.get("provider")),
            requested_mode=_optional_str(values.get("requested_mode")),
            policy_ref=_optional_str(values.get("policy_ref")),
            approval_context=_mapping(
                values.get("approval_context", {}),
                "approval_context",
            ),
            correlation_id=_optional_str(values.get("correlation_id")),
        )


@dataclass(frozen=True)
class HostToolResult:
    """Structured result returned by the host compatibility layer."""

    status: HostResultStatus
    tool_name: str
    capability: str | None
    target: str
    provider: str
    reason: str
    data: Mapping[str, Any] = field(default_factory=dict)
    approval_request_id: str | None = None
    risks: tuple[str, ...] = ()
    redactions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        safe_data, redactions = redact_mapping(dict(self.data))
        all_redactions = tuple(self.redactions) + tuple(f"data.{path}" for path in redactions)
        object.__setattr__(self, "reason", _redact_text(self.reason))
        object.__setattr__(self, "data", MappingProxyType(dict(safe_data)))
        object.__setattr__(self, "redactions", all_redactions)

    @classmethod
    def from_adapter_result(cls, payload: Mapping[str, Any]) -> "HostToolResult":
        """Build a host result from an SDK adapter result payload."""

        return cls(
            status=_status_from_value(payload.get("status")),
            tool_name=_optional_string(payload.get("tool_name"), default=""),
            capability=_nullable_string(payload.get("capability")),
            target=_optional_string(payload.get("target"), default=""),
            provider=_optional_string(payload.get("provider"), default=""),
            reason=_optional_string(payload.get("reason"), default=""),
            data=_mapping(payload.get("data", {}), "data"),
            approval_request_id=_nullable_string(payload.get("approval_request_id")),
            risks=tuple(str(item) for item in payload.get("risks", ())),
            redactions=tuple(str(item) for item in payload.get("redactions", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe result dictionary."""

        payload: dict[str, Any] = {
            "status": self.status.value,
            "tool_name": self.tool_name,
            "capability": self.capability,
            "target": self.target,
            "provider": self.provider,
            "reason": self.reason,
            "data": dict(self.data),
            "risks": list(self.risks),
            "redactions": sorted(set(self.redactions)),
        }
        if self.approval_request_id is not None:
            payload["approval_request_id"] = self.approval_request_id
        return _json_safe(payload)


@dataclass(frozen=True)
class HostError:
    """Structured error returned to the host compatibility caller."""

    status: HostResultStatus
    reason: str
    tool_name: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in (
            HostResultStatus.VALIDATION_ERROR,
            HostResultStatus.PROVIDER_ERROR,
            HostResultStatus.POLICY_ERROR,
        ):
            raise ValueError("host errors must use an error status")
        safe_details, redactions = redact_mapping(dict(self.details))
        object.__setattr__(self, "reason", _redact_text(self.reason))
        object.__setattr__(self, "details", MappingProxyType(dict(safe_details)))
        object.__setattr__(self, "_redactions", tuple(f"details.{path}" for path in redactions))

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        *,
        status: HostResultStatus = HostResultStatus.VALIDATION_ERROR,
        tool_name: str | None = None,
    ) -> "HostError":
        """Build a host-safe error from an exception."""

        return cls(status=status, reason=str(exc), tool_name=tool_name)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe error dictionary."""

        payload: dict[str, Any] = {
            "status": self.status.value,
            "reason": self.reason,
            "details": dict(self.details),
            "redactions": sorted(set(getattr(self, "_redactions", ()))),
        }
        if self.tool_name is not None:
            payload["tool_name"] = self.tool_name
        return _json_safe(payload)


def _status_from_value(value: Any) -> HostResultStatus:
    if isinstance(value, HostResultStatus):
        return value
    if isinstance(value, str):
        try:
            return HostResultStatus(value)
        except ValueError:
            pass
    return HostResultStatus.VALIDATION_ERROR


def _required_str(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"host {key} is required")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("host optional string fields must be strings")
    return value


def _optional_string(value: Any, *, default: str) -> str:
    return value if isinstance(value, str) else default


def _nullable_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"host {name} must be an object")
    return value


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
    """Return a JSON-compatible copy of a value."""

    return json.loads(json.dumps(value, sort_keys=True))


__all__ = [
    "HOST_RESULT_STATUSES",
    "HostError",
    "HostResultStatus",
    "HostToolCall",
    "HostToolDescriptor",
    "HostToolResult",
    "HostToolSchema",
]
