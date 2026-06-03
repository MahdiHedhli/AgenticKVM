import inspect

from agentickvm.control_plane import (
    ControlMode,
    InMemoryAuditSink,
    TargetDefinition,
    TargetRegistry,
    mode_preset,
)
from agentickvm.mcp import (
    MCPResultStatus,
    MCPRouter,
    MCPToolDefinition,
    MCPToolRequest,
)
from agentickvm.mcp import router as router_module
from agentickvm.providers import MockProvider, ProviderEntry, ProviderRegistry


class BadMappingRegistry:
    def get(self, tool_name: str):
        if tool_name == "bad_mapping":
            return MCPToolDefinition(
                tool_name="bad_mapping",
                capability_id="provider.raw_reset",
                description="bad mapping",
            )
        return None


def _router(mode: ControlMode = ControlMode.FULL_CONTROL):
    sink = InMemoryAuditSink()
    provider = MockProvider()
    provider_registry = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                provider=provider,
            )
        ]
    )
    target_registry = TargetRegistry(
        provider_registry=provider_registry,
        targets=[TargetDefinition(target_id="lab-a", provider_id="mock")],
    )
    return (
        MCPRouter(
            provider_registry=provider_registry,
            target_registry=target_registry,
            policy=mode_preset(mode),
            audit_sink=sink,
        ),
        provider,
        sink,
    )


def _request(tool_name: str, **params) -> MCPToolRequest:
    return MCPToolRequest(
        tool_name=tool_name,
        target="lab-a",
        session_id="s1",
        requester_id="agent-1",
        provider="mock",
        params=params,
    )


def test_mcp_router_source_does_not_call_provider_directly() -> None:
    source = inspect.getsource(router_module.MCPRouter)

    assert "execute_authorized" not in source
    assert "MockProvider" not in source


def test_mapped_unknown_capability_fails_closed_without_provider_call() -> None:
    router, provider, sink = _router(ControlMode.FULL_CONTROL)
    router = MCPRouter(
        provider_registry=router.provider_registry,
        target_registry=router.target_registry,
        policy=router.policy,
        audit_sink=router.audit_sink,
        registry=BadMappingRegistry(),
    )

    result = router.handle_tool_request(_request("bad_mapping"))

    assert result.status == MCPResultStatus.POLICY_ERROR
    assert result.reason == "unknown mapped capability"
    assert provider.requests == []
    assert len(sink.events) == 1


def test_full_control_cannot_modify_policy_through_mcp() -> None:
    router, provider, sink = _router(ControlMode.FULL_CONTROL)

    result = router.handle_tool_request(_request("modify_policy"))

    assert result.status == MCPResultStatus.DENIED
    assert result.capability == "session.modify_policy"
    assert result.reason == "hard invariant"
    assert provider.requests == []
    assert any(event.event_type.value == "policy_decision" for event in sink.events)


def test_raw_secret_reveal_is_denied_through_mcp() -> None:
    router, provider, _sink = _router(ControlMode.FULL_CONTROL)

    result = router.handle_tool_request(_request("reveal_secret", secret_name="root"))

    assert result.status == MCPResultStatus.DENIED
    assert result.capability == "secrets.raw_reveal"
    assert provider.requests == []
    assert result.reason == "missing required credential scope"


def test_denied_mcp_action_preserves_audit_behavior() -> None:
    router, provider, sink = _router(ControlMode.OBSERVE)

    result = router.handle_tool_request(_request("power_on"))

    assert result.status == MCPResultStatus.DENIED
    assert provider.requests == []
    assert [event.event_type.value for event in sink.events] == [
        "request_received",
        "capability_resolved",
        "policy_decision",
        "result_returned",
    ]


def test_no_real_provider_is_used_in_mcp_tests() -> None:
    _router_instance, provider, _sink = _router(ControlMode.FULL_CONTROL)

    assert provider.provider_id == "mock"
    assert provider.is_real_hardware is False
