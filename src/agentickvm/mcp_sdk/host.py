"""Mock-only MCP host compatibility adapter.

This module provides a local, dependency-free compatibility boundary for
future MCP host behavior. It does not open listeners, import a live SDK, resolve
credentials, or execute providers directly.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from agentickvm.config import ConfigRuntime
from agentickvm.mcp_sdk.adapter import MCPSDKAdapter
from agentickvm.mcp_sdk.host_models import (
    HostError,
    HostResultStatus,
    HostToolCall,
    HostToolDescriptor,
    HostToolResult,
    HostToolSchema,
)
from agentickvm.mcp_sdk.models import MCPSDKToolCall


class MCPHostCompatibilityLayer:
    """Local host compatibility layer over the mock-only SDK adapter."""

    def __init__(
        self,
        *,
        adapter: MCPSDKAdapter | None = None,
        runtime: ConfigRuntime | None = None,
        config_path: str | None = None,
        adapter_factory: type[MCPSDKAdapter] = MCPSDKAdapter,
    ) -> None:
        if adapter is not None and (runtime is not None or config_path is not None):
            raise ValueError("provide either adapter or runtime/config_path, not both")
        self.adapter = adapter or adapter_factory(
            runtime=runtime,
            config_path=config_path,
        )

    @classmethod
    def mock_only(cls) -> "MCPHostCompatibilityLayer":
        """Return a host layer using the built-in safe mock-only config."""

        return cls()

    @classmethod
    def from_config(cls, config_path: str) -> "MCPHostCompatibilityLayer":
        """Return a host layer from an explicit safe config path."""

        return cls(config_path=config_path)

    def list_tools(self) -> dict[str, Any]:
        """Return JSON-safe host tool descriptors."""

        try:
            tools = [
                HostToolDescriptor(
                    tool_name=_required_adapter_str(tool, "tool_name"),
                    capability=_required_adapter_str(tool, "capability"),
                    description=_required_adapter_str(tool, "description"),
                    dangerous=bool(tool.get("dangerous", False)),
                ).to_dict()
                for tool in self.adapter.list_tools()
            ]
        except Exception as exc:  # pragma: no cover - covered through behavior
            return self.serialize_error(exc)
        return _json_safe({"status": HostResultStatus.OK.value, "tools": tools})

    def get_tool_schema(self, tool_name: str) -> dict[str, Any]:
        """Return a JSON-safe schema for one tool."""

        if not tool_name:
            return HostError(
                status=HostResultStatus.VALIDATION_ERROR,
                reason="host tool_name is required",
            ).to_dict()
        payload = self.adapter.tool_schema(tool_name)
        if payload.get("status") != HostResultStatus.OK.value:
            return HostError(
                status=HostResultStatus.VALIDATION_ERROR,
                reason=str(payload.get("reason", "tool schema unavailable")),
                tool_name=tool_name,
                details={"adapter_status": payload.get("status")},
            ).to_dict()
        try:
            return HostToolSchema.from_adapter_schema(payload).to_dict()
        except Exception as exc:  # pragma: no cover - defensive
            return self.serialize_error(exc, tool_name=tool_name)

    def tool_schema(self, tool_name: str) -> dict[str, Any]:
        """Alias for compatibility with adapter-style callers."""

        return self.get_tool_schema(tool_name)

    def call_tool(self, request: HostToolCall | Mapping[str, Any]) -> dict[str, Any]:
        """Route a host-style tool call through the SDK adapter."""

        try:
            host_call = (
                request if isinstance(request, HostToolCall) else HostToolCall.from_mapping(request)
            )
            adapter_result = self.adapter.call_tool(
                MCPSDKToolCall(
                    tool_name=host_call.tool_name,
                    target=host_call.target,
                    session_id=host_call.session_id,
                    requester_id=host_call.requester_id,
                    params=host_call.params,
                    provider=host_call.provider,
                    requested_mode=host_call.requested_mode,
                    policy_ref=host_call.policy_ref,
                    approval_context=host_call.approval_context,
                    correlation_id=host_call.correlation_id,
                )
            )
            return HostToolResult.from_adapter_result(adapter_result).to_dict()
        except Exception as exc:
            tool_name = request.tool_name if isinstance(request, HostToolCall) else None
            if isinstance(request, Mapping) and isinstance(request.get("tool_name"), str):
                tool_name = request["tool_name"]
            return self.serialize_error(exc, tool_name=tool_name)

    def serialize_result(self, result: HostToolResult | Mapping[str, Any]) -> dict[str, Any]:
        """Return a JSON-safe host result payload."""

        if isinstance(result, HostToolResult):
            return result.to_dict()
        return HostToolResult.from_adapter_result(result).to_dict()

    def serialize_error(
        self,
        exc: Exception,
        *,
        status: HostResultStatus = HostResultStatus.VALIDATION_ERROR,
        tool_name: str | None = None,
    ) -> dict[str, Any]:
        """Return a JSON-safe host error payload."""

        return HostError.from_exception(exc, status=status, tool_name=tool_name).to_dict()


def _required_adapter_str(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"adapter tool metadata missing {key}")
    return value


def _json_safe(value: Any) -> Any:
    """Return a JSON-compatible copy of a value."""

    return json.loads(json.dumps(value, sort_keys=True))


__all__ = ["MCPHostCompatibilityLayer"]
