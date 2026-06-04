from pathlib import Path
from typing import Any, Mapping

from agentickvm.config import build_runtime, config_from_mapping
from agentickvm.control_plane import CapabilityRequest, ControlPlane
from agentickvm.mcp import MCPRouter, MCPToolRequest
from agentickvm.mcp_sdk import MCPHostCompatibilityLayer, MCPSDKAdapter
from agentickvm.mcp_sdk.models import MCPSDKToolCall

ROOT = Path(__file__).resolve().parents[2]


class SpyAdapter:
    listed = False
    schemas: list[str] = []
    calls: list[MCPSDKToolCall] = []

    def list_tools(self) -> list[dict[str, Any]]:
        self.listed = True
        return [
            {
                "tool_name": "observe_screen",
                "capability": "observe.screenshot",
                "description": "Observe screen.",
                "dangerous": False,
            }
        ]

    def tool_schema(self, tool_name: str) -> dict[str, Any]:
        self.schemas.append(tool_name)
        return {
            "status": "ok",
            "tool_name": tool_name,
            "capability": "observe.screenshot",
            "description": "Observe screen.",
            "dangerous": False,
            "input": {"type": "object", "required": ["target"]},
        }

    def call_tool(self, request: MCPSDKToolCall | Mapping[str, Any]) -> dict[str, Any]:
        assert isinstance(request, MCPSDKToolCall)
        self.calls.append(request)
        return {
            "status": "ok",
            "tool_name": request.tool_name,
            "capability": "observe.screenshot",
            "target": request.target,
            "provider": "mock-provider",
            "reason": "ok",
            "data": {"provider_result": {"performed_on_hardware": False}},
            "risks": [],
            "redactions": [],
        }


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


def test_mcp_host_routes_list_schema_and_calls_through_sdk_adapter() -> None:
    adapter = SpyAdapter()
    host = MCPHostCompatibilityLayer(adapter=adapter)  # type: ignore[arg-type]

    tools = host.list_tools()
    schema = host.get_tool_schema("observe_screen")
    result = host.call_tool(
        {
            "tool_name": "observe_screen",
            "target": "mock-host",
            "session_id": "host-s1",
            "requester_id": "host-test",
        }
    )

    assert tools["status"] == "ok"
    assert adapter.listed is True
    assert schema["status"] == "ok"
    assert adapter.schemas == ["observe_screen"]
    assert result["status"] == "ok"
    assert adapter.calls[0].tool_name == "observe_screen"
    assert adapter.calls[0].target == "mock-host"


def test_mcp_host_routes_through_mcp_router_and_control_plane() -> None:
    SpyRouter.handled = []
    SpyControlPlane.handled = []
    adapter = MCPSDKAdapter(
        router_factory=SpyRouter,
        control_plane_factory=SpyControlPlane,
    )
    host = MCPHostCompatibilityLayer(adapter=adapter)

    result = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "mock-host",
            "session_id": "host-s1",
            "requester_id": "host-test",
            "correlation_id": "host-contract-power",
        }
    )

    assert result["status"] == "ok"
    assert SpyRouter.handled[0].tool_name == "get_power_state"
    assert SpyControlPlane.handled[0].capability_id == "observe.power_state"


def test_mcp_host_unknown_target_fails_closed() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    result = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "missing-target",
            "session_id": "host-s1",
            "requester_id": "host-test",
        }
    )

    assert result["status"] == "validation_error"
    assert "Unknown target id" in result["reason"]


def test_mcp_host_disabled_provider_fails_closed() -> None:
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
    host = MCPHostCompatibilityLayer(runtime=runtime)

    result = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "redfish-target",
            "session_id": "host-s1",
            "requester_id": "host-test",
        }
    )

    assert result["status"] == "validation_error"
    assert "non-executable provider" in result["reason"]


def test_mcp_host_pikvm_fixture_observe_succeeds() -> None:
    host = MCPHostCompatibilityLayer.from_config(
        str(ROOT / "examples" / "config" / "pikvm-observe-fixture.yaml")
    )

    result = host.call_tool(
        {
            "tool_name": "observe_screen",
            "target": "pikvm-fixture-target",
            "session_id": "host-s1",
            "requester_id": "host-test",
            "provider": "pikvm-fixture",
        }
    )

    assert result["status"] == "ok"
    provider_result = result["data"]["provider_result"]
    assert provider_result["provider_type"] == "pikvm"
    assert provider_result["performed_on_hardware"] is False
    assert provider_result["data"]["screenshot"]["raw_bytes_included"] is False


def test_mcp_host_dangerous_action_preserves_approval_required() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    result = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "host-s1",
            "requester_id": "host-test",
        }
    )

    assert result["status"] == "approval_required"
    assert result["capability"] == "power.force_restart"
    assert "approval_request_id" in result


def test_mcp_host_raw_secret_and_policy_modification_are_denied() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    secret = host.call_tool(
        {
            "tool_name": "reveal_secret",
            "target": "mock-host",
            "session_id": "host-s1",
            "requester_id": "host-test",
        }
    )
    policy = host.call_tool(
        {
            "tool_name": "modify_policy",
            "target": "mock-host",
            "session_id": "host-s1",
            "requester_id": "host-test",
        }
    )

    assert secret["status"] == "denied"
    assert policy["status"] == "denied"
