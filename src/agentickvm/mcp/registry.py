"""MCP tool-to-capability registry."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping

from agentickvm.control_plane import (
    CapabilityRegistry,
    DEFAULT_CAPABILITY_REGISTRY,
)


@dataclass(frozen=True)
class MCPToolDefinition:
    """Mapping from a tool name to a provider-neutral capability."""

    tool_name: str
    capability_id: str
    description: str
    dangerous: bool = False


class MCPToolRegistry:
    """Immutable registry for known MCP-style tools."""

    def __init__(
        self,
        tools: Iterable[MCPToolDefinition],
        *,
        capability_registry: CapabilityRegistry = DEFAULT_CAPABILITY_REGISTRY,
    ) -> None:
        registry: dict[str, MCPToolDefinition] = {}
        for tool in tools:
            if tool.tool_name in registry:
                raise ValueError(f"Duplicate MCP tool name: {tool.tool_name}")
            if capability_registry.get(tool.capability_id) is None:
                raise ValueError(
                    f"MCP tool {tool.tool_name} maps to unknown capability "
                    f"{tool.capability_id}"
                )
            registry[tool.tool_name] = tool
        self._tools: Mapping[str, MCPToolDefinition] = MappingProxyType(registry)

    @property
    def tools(self) -> Mapping[str, MCPToolDefinition]:
        """Return known tool mappings."""

        return self._tools

    def get(self, tool_name: str) -> MCPToolDefinition | None:
        """Return a tool definition, or None if unknown."""

        return self._tools.get(tool_name)

    def capability_for(self, tool_name: str) -> str | None:
        """Return the mapped capability id, or None if unknown."""

        tool = self.get(tool_name)
        return tool.capability_id if tool is not None else None


DEFAULT_MCP_TOOLS: tuple[MCPToolDefinition, ...] = (
    MCPToolDefinition(
        tool_name="observe_screen",
        capability_id="observe.screenshot",
        description="Observe the current screen through the control plane.",
    ),
    MCPToolDefinition(
        tool_name="get_status",
        capability_id="observe.status",
        description="Read a provider-neutral target status summary.",
    ),
    MCPToolDefinition(
        tool_name="get_power_state",
        capability_id="observe.power_state",
        description="Read target power state.",
    ),
    MCPToolDefinition(
        tool_name="power_on",
        capability_id="power.on",
        description="Power on an in-scope target.",
        dangerous=True,
    ),
    MCPToolDefinition(
        tool_name="graceful_restart",
        capability_id="power.graceful_restart",
        description="Request an orderly restart.",
        dangerous=True,
    ),
    MCPToolDefinition(
        tool_name="force_restart",
        capability_id="power.force_restart",
        description="Force an immediate restart.",
        dangerous=True,
    ),
    MCPToolDefinition(
        tool_name="mount_media",
        capability_id="media.mount_approved_iso",
        description="Mount pre-approved virtual media.",
        dangerous=True,
    ),
    MCPToolDefinition(
        tool_name="change_boot_order",
        capability_id="boot.override",
        description="Set a boot override.",
        dangerous=True,
    ),
    MCPToolDefinition(
        tool_name="type_text",
        capability_id="input.keyboard_type",
        description="Type text through a remote input device.",
        dangerous=True,
    ),
    MCPToolDefinition(
        tool_name="modify_policy",
        capability_id="session.modify_policy",
        description="Attempt to modify active policy.",
        dangerous=True,
    ),
    MCPToolDefinition(
        tool_name="reveal_secret",
        capability_id="secrets.raw_reveal",
        description="Attempt to reveal raw secret material.",
        dangerous=True,
    ),
)

DEFAULT_MCP_TOOL_REGISTRY = MCPToolRegistry(DEFAULT_MCP_TOOLS)
