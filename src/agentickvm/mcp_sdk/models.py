"""JSON-safe models for the dependency-free MCP SDK adapter scaffold."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True)
class MCPSDKToolCall:
    """Tool-call shape accepted by the internal MCP SDK adapter."""

    tool_name: str
    target: str
    session_id: str = "sdk-session"
    requester_id: str = "mcp-sdk"
    params: Mapping[str, Any] = field(default_factory=dict)
    provider: str | None = None
    requested_mode: str | None = None
    policy_ref: str | None = None
    approval_context: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.tool_name:
            raise ValueError("MCP SDK tool_name is required")
        if not self.target:
            raise ValueError("MCP SDK target is required")
        if not self.session_id:
            raise ValueError("MCP SDK session_id is required")
        if not self.requester_id:
            raise ValueError("MCP SDK requester_id is required")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        object.__setattr__(
            self,
            "approval_context",
            MappingProxyType(dict(self.approval_context)),
        )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "MCPSDKToolCall":
        """Build a tool call from a JSON-like mapping."""

        return cls(
            tool_name=_required_str(values, "tool_name"),
            target=_required_str(values, "target"),
            session_id=str(values.get("session_id", "sdk-session")),
            requester_id=str(values.get("requester_id", "mcp-sdk")),
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


def _required_str(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"MCP SDK {key} is required")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("MCP SDK optional string fields must be strings")
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"MCP SDK {name} must be an object")
    return value


__all__ = ["MCPSDKToolCall"]
