from agentickvm.control_plane import ControlMode, mode_preset
from agentickvm.control_plane.targets import TargetDefinition, TargetRegistry
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest
from agentickvm.mcp.registry import DEFAULT_MCP_TOOL_REGISTRY
from agentickvm.providers import MockProvider, ProviderEntry, ProviderRegistry


def _router() -> MCPRouter:
    providers = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                provider=MockProvider(),
            )
        ]
    )
    targets = TargetRegistry(
        provider_registry=providers,
        targets=[TargetDefinition(target_id="mock-host", provider_id="mock")],
    )
    return MCPRouter(
        provider_registry=providers,
        target_registry=targets,
        policy=mode_preset(ControlMode.FULL_CONTROL),
    )


def _request(tool_name: str) -> MCPToolRequest:
    return MCPToolRequest(
        tool_name=tool_name,
        target="mock-host",
        provider="mock",
        session_id="approval-tool-policy-session",
        requester_id="agent",
    )


def test_mcp_exposes_request_and_deny_approval_only() -> None:
    tools = DEFAULT_MCP_TOOL_REGISTRY.tools

    assert "request_approval" in tools
    assert "deny_approval" in tools
    assert tools["request_approval"].capability_id == "runtime.request_approval"
    assert tools["deny_approval"].capability_id == "runtime.deny_approval"

    for forbidden in (
        "grant_approval",
        "approve_approval",
        "approval_grant",
        "sign_grant",
        "consume_grant",
    ):
        assert forbidden not in tools


def test_mcp_grant_and_approve_tool_names_fail_closed() -> None:
    router = _router()

    for forbidden in ("grant_approval", "approve_approval", "sign_grant"):
        result = router.handle_tool_request(_request(forbidden))

        assert result.status == MCPResultStatus.VALIDATION_ERROR
        assert result.reason == "unknown MCP tool"


def test_mcp_request_and_deny_approval_route_through_control_plane() -> None:
    router = _router()

    request_result = router.handle_tool_request(_request("request_approval"))
    deny_result = router.handle_tool_request(_request("deny_approval"))

    assert request_result.status == MCPResultStatus.OK
    assert request_result.capability == "runtime.request_approval"
    assert deny_result.status == MCPResultStatus.OK
    assert deny_result.capability == "runtime.deny_approval"
