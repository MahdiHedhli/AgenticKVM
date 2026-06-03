import pytest

from agentickvm.mcp import DEFAULT_MCP_TOOL_REGISTRY, MCPToolDefinition, MCPToolRegistry


def test_known_mcp_tools_map_to_expected_capabilities() -> None:
    assert DEFAULT_MCP_TOOL_REGISTRY.capability_for("observe_screen") == "observe.screenshot"
    assert DEFAULT_MCP_TOOL_REGISTRY.capability_for("get_power_state") == "observe.power_state"
    assert (
        DEFAULT_MCP_TOOL_REGISTRY.capability_for("get_hardware_inventory")
        == "observe.hardware_inventory"
    )
    assert DEFAULT_MCP_TOOL_REGISTRY.capability_for("get_sensors") == "observe.sensors"
    assert DEFAULT_MCP_TOOL_REGISTRY.capability_for("get_event_logs") == "observe.event_logs"
    assert DEFAULT_MCP_TOOL_REGISTRY.capability_for("get_boot_status") == "observe.boot_status"
    assert DEFAULT_MCP_TOOL_REGISTRY.capability_for("power_on") == "power.on"
    assert DEFAULT_MCP_TOOL_REGISTRY.capability_for("graceful_restart") == "power.graceful_restart"
    assert DEFAULT_MCP_TOOL_REGISTRY.capability_for("force_restart") == "power.force_restart"
    assert DEFAULT_MCP_TOOL_REGISTRY.capability_for("mount_media") == "media.mount_approved_iso"
    assert DEFAULT_MCP_TOOL_REGISTRY.capability_for("change_boot_order") == "boot.override"


def test_unknown_mcp_tool_has_no_capability_mapping() -> None:
    assert DEFAULT_MCP_TOOL_REGISTRY.capability_for("provider_raw_reset") is None


def test_unknown_capability_mapping_fails_closed_at_registry_build() -> None:
    with pytest.raises(ValueError, match="unknown capability"):
        MCPToolRegistry(
            [
                MCPToolDefinition(
                    tool_name="bad_tool",
                    capability_id="provider.raw_reset",
                    description="bad mapping",
                )
            ]
        )


def test_duplicate_mcp_tool_names_fail_closed() -> None:
    with pytest.raises(ValueError, match="Duplicate MCP tool name"):
        MCPToolRegistry(
            [
                MCPToolDefinition(
                    tool_name="dup",
                    capability_id="observe.status",
                    description="one",
                ),
                MCPToolDefinition(
                    tool_name="dup",
                    capability_id="observe.power_state",
                    description="two",
                ),
            ]
        )
