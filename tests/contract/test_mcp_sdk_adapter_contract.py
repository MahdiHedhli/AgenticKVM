from pathlib import Path

from agentickvm.config import build_runtime, config_from_mapping
from agentickvm.control_plane import CapabilityRequest, ControlPlane
from agentickvm.mcp import MCPRouter, MCPToolRequest
from agentickvm.mcp_sdk import MCPSDKAdapter

ROOT = Path(__file__).resolve().parents[2]


class SpyRouter(MCPRouter):
    handled: list[MCPToolRequest] = []

    def handle_tool_request(self, request: MCPToolRequest):
        self.handled.append(request)
        return super().handle_tool_request(request)


class SpyControlPlane(ControlPlane):
    handled: list[CapabilityRequest] = []

    def handle(self, request: CapabilityRequest):
        self.handled.append(request)
        return super().handle(request)


def test_mcp_sdk_adapter_routes_through_mcp_router_and_control_plane() -> None:
    SpyRouter.handled = []
    SpyControlPlane.handled = []
    adapter = MCPSDKAdapter(
        router_factory=SpyRouter,
        control_plane_factory=SpyControlPlane,
    )

    result = adapter.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "mock-host",
            "session_id": "s1",
            "requester_id": "sdk-test",
            "correlation_id": "sdk-contract-power",
        }
    )

    assert result["status"] == "ok"
    assert SpyRouter.handled[0].tool_name == "get_power_state"
    assert SpyControlPlane.handled[0].capability_id == "observe.power_state"


def test_mcp_sdk_adapter_unknown_target_fails_closed() -> None:
    adapter = MCPSDKAdapter.mock_only()

    result = adapter.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "missing-target",
            "session_id": "s1",
            "requester_id": "sdk-test",
        }
    )

    assert result["status"] == "validation_error"
    assert "Unknown target id" in result["reason"]


def test_mcp_sdk_adapter_disabled_provider_fails_closed() -> None:
    runtime = build_runtime(
        config_from_mapping(
            {
                "version": "0.1",
                "providers": [
                    {
                        "id": "redfish-disabled",
                        "type": "redfish",
                        "enabled": False,
                    }
                ],
                "targets": [
                    {
                        "id": "redfish-target",
                        "provider": "redfish-disabled",
                        "enabled": True,
                        "allowed_modes": ["Observe"],
                    }
                ],
                "default_policy": {"mode": "Observe"},
            }
        )
    )
    adapter = MCPSDKAdapter(runtime=runtime)

    result = adapter.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "redfish-target",
            "session_id": "s1",
            "requester_id": "sdk-test",
        }
    )

    assert result["status"] == "validation_error"
    assert "non-executable provider" in result["reason"]


def test_mcp_sdk_adapter_pikvm_fixture_observe_succeeds() -> None:
    adapter = MCPSDKAdapter.from_config(
        str(ROOT / "examples" / "config" / "pikvm-observe-fixture.yaml")
    )

    result = adapter.call_tool(
        {
            "tool_name": "observe_screen",
            "target": "pikvm-fixture-target",
            "session_id": "s1",
            "requester_id": "sdk-test",
            "provider": "pikvm-fixture",
        }
    )

    assert result["status"] == "ok"
    provider_result = result["data"]["provider_result"]
    assert provider_result["provider_type"] == "pikvm"
    assert provider_result["performed_on_hardware"] is False
    assert provider_result["data"]["screenshot"]["raw_bytes_included"] is False


def test_mcp_sdk_adapter_dangerous_action_returns_approval_required() -> None:
    adapter = MCPSDKAdapter.mock_only()

    result = adapter.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "s1",
            "requester_id": "sdk-test",
        }
    )

    assert result["status"] == "approval_required"
    assert result["capability"] == "power.force_restart"
    assert "approval_request_id" in result


def test_mcp_sdk_adapter_raw_secret_and_policy_modification_are_denied() -> None:
    adapter = MCPSDKAdapter.mock_only()

    secret = adapter.call_tool(
        {
            "tool_name": "reveal_secret",
            "target": "mock-host",
            "session_id": "s1",
            "requester_id": "sdk-test",
        }
    )
    policy = adapter.call_tool(
        {
            "tool_name": "modify_policy",
            "target": "mock-host",
            "session_id": "s1",
            "requester_id": "sdk-test",
        }
    )

    assert secret["status"] == "denied"
    assert policy["status"] == "denied"
