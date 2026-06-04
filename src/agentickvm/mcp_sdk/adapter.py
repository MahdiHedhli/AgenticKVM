"""Dependency-free MCP SDK adapter scaffold.

This adapter models the future MCP SDK boundary without importing an SDK,
opening a listener, resolving credentials, or reaching live providers.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from agentickvm.config import ConfigRuntime, build_runtime, load_config
from agentickvm.control_plane import ControlPlane
from agentickvm.mcp import (
    DEFAULT_MCP_TOOL_REGISTRY,
    MCPRouter,
    MCPToolRegistry,
    MCPToolRequest,
)
from agentickvm.mcp_sdk.models import MCPSDKToolCall


class MCPSDKAdapter:
    """Mock-only adapter over the existing MCP router."""

    def __init__(
        self,
        *,
        runtime: ConfigRuntime | None = None,
        config_path: str | None = None,
        registry: MCPToolRegistry = DEFAULT_MCP_TOOL_REGISTRY,
        router_factory: type[MCPRouter] = MCPRouter,
        control_plane_factory: type[ControlPlane] = ControlPlane,
    ) -> None:
        self.runtime = runtime or build_runtime(load_config(config_path))
        self.registry = registry
        self.router = router_factory(
            provider_registry=self.runtime.provider_registry,
            target_registry=self.runtime.target_registry,
            policy=self.runtime.policy,
            audit_sink=self.runtime.audit_sink,
            registry=registry,
            control_plane_factory=control_plane_factory,
        )

    @classmethod
    def mock_only(cls) -> "MCPSDKAdapter":
        """Return an adapter using the built-in safe mock-only config."""

        return cls()

    @classmethod
    def from_config(cls, config_path: str) -> "MCPSDKAdapter":
        """Return an adapter from an explicit safe config path."""

        return cls(config_path=config_path)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return JSON-safe registered tool metadata."""

        return _json_safe(
            [
                {
                    "tool_name": tool.tool_name,
                    "capability": tool.capability_id,
                    "description": tool.description,
                    "dangerous": tool.dangerous,
                }
                for tool in self.registry.tools.values()
            ]
        )

    def tool_schema(self, tool_name: str) -> dict[str, Any]:
        """Return a small JSON-safe schema for one registered tool."""

        tool = self.registry.get(tool_name)
        if tool is None:
            return {
                "status": "validation_error",
                "tool_name": tool_name,
                "reason": "unknown MCP tool",
            }
        return {
            "status": "ok",
            "tool_name": tool.tool_name,
            "capability": tool.capability_id,
            "description": tool.description,
            "dangerous": tool.dangerous,
            "input": {
                "type": "object",
                "required": ["target"],
                "properties": {
                    "target": {"type": "string"},
                    "params": {"type": "object"},
                    "provider": {"type": "string"},
                    "session_id": {"type": "string"},
                    "requester_id": {"type": "string"},
                    "correlation_id": {"type": "string"},
                },
            },
        }

    def call_tool(self, request: MCPSDKToolCall | Mapping[str, Any]) -> dict[str, Any]:
        """Route a JSON-like tool call through `MCPRouter`."""

        tool_call = (
            request
            if isinstance(request, MCPSDKToolCall)
            else MCPSDKToolCall.from_mapping(request)
        )
        result = self.router.handle_tool_request(
            MCPToolRequest(
                tool_name=tool_call.tool_name,
                target=tool_call.target,
                session_id=tool_call.session_id,
                requester_id=tool_call.requester_id,
                params=tool_call.params,
                provider=tool_call.provider,
                requested_mode=tool_call.requested_mode,
                policy_ref=tool_call.policy_ref,
                approval_context=tool_call.approval_context,
                correlation_id=tool_call.correlation_id,
            )
        )
        return _json_safe(result.to_dict())


def _json_safe(value: Any) -> Any:
    """Return a JSON-compatible copy of a value."""

    return json.loads(json.dumps(value, sort_keys=True))


__all__ = ["MCPSDKAdapter"]
