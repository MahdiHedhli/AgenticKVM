from agentickvm.control_plane import (
    Actor,
    ActorType,
    CapabilityRequest,
    ControlMode,
    ControlPlane,
    InMemoryAuditSink,
    mode_preset,
)
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest
from agentickvm.providers import MockProvider


class SpyControlPlane(ControlPlane):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.handled_requests: list[CapabilityRequest] = []

    def handle(self, request: CapabilityRequest):
        self.handled_requests.append(request)
        return super().handle(request)


def _router(mode: ControlMode = ControlMode.FULL_CONTROL):
    sink = InMemoryAuditSink()
    provider = MockProvider()
    control_plane = SpyControlPlane(
        policy=mode_preset(mode),
        provider=provider,
        audit_sink=sink,
    )
    return MCPRouter(control_plane=control_plane), control_plane, provider, sink


def _request(tool_name: str, **params) -> MCPToolRequest:
    return MCPToolRequest(
        tool_name=tool_name,
        target="lab-a",
        session_id="s1",
        requester_id="agent-1",
        provider="mock",
        params=params,
        requested_mode="Full Control",
        correlation_id=f"corr-{tool_name}",
    )


def test_mcp_router_imports() -> None:
    router, control_plane, provider, sink = _router()

    assert isinstance(router, MCPRouter)
    assert control_plane.provider is provider
    assert sink.events == []


def test_observe_tool_succeeds_through_mock_provider_when_policy_allows() -> None:
    router, control_plane, provider, sink = _router(ControlMode.FULL_CONTROL)

    result = router.handle_tool_request(_request("get_power_state"))
    payload = result.to_dict()

    assert result.status == MCPResultStatus.OK
    assert payload["capability"] == "observe.power_state"
    assert payload["provider"] == "mock"
    assert control_plane.handled_requests[0].capability_id == "observe.power_state"
    assert provider.requests[0].capability == "observe.power_state"
    assert any(event.event_type.value == "provider_execution_completed" for event in sink.events)


def test_unknown_tool_fails_closed_without_provider_call() -> None:
    router, control_plane, provider, sink = _router(ControlMode.FULL_CONTROL)

    result = router.handle_tool_request(_request("provider_raw_reset"))

    assert result.status == MCPResultStatus.VALIDATION_ERROR
    assert result.reason == "unknown MCP tool"
    assert control_plane.handled_requests == []
    assert provider.requests == []
    assert len(sink.events) == 1


def test_dangerous_tool_returns_approval_required_under_supervised_policy() -> None:
    router, control_plane, provider, _sink = _router(ControlMode.SUPERVISED)

    result = router.handle_tool_request(_request("force_restart"))

    assert result.status == MCPResultStatus.APPROVAL_REQUIRED
    assert result.capability == "power.force_restart"
    assert result.approval_request_id is not None
    assert "dangerous action" in result.risks
    assert control_plane.handled_requests[0].capability_id == "power.force_restart"
    assert provider.requests == []


def test_approval_required_result_redacts_params_preview() -> None:
    router, _control_plane, provider, _sink = _router(ControlMode.SUPERVISED)

    result = router.handle_tool_request(
        _request("type_text", text="operator typed secret", password="hidden")
    )
    payload = result.to_dict()

    assert result.status == MCPResultStatus.APPROVAL_REQUIRED
    assert payload["data"]["params_preview"]["text"] == "[REDACTED]"
    assert payload["data"]["params_preview"]["password"] == "[REDACTED]"
    assert set(payload["redactions"]) == {"params.text", "params.password"}
    assert provider.requests == []


def test_requested_mode_does_not_self_escalate_policy() -> None:
    router, _control_plane, provider, _sink = _router(ControlMode.SUPERVISED)
    request = _request("force_restart")

    result = router.handle_tool_request(request)

    assert result.status == MCPResultStatus.APPROVAL_REQUIRED
    assert provider.requests == []


def test_unknown_provider_fails_closed() -> None:
    router, control_plane, provider, sink = _router(ControlMode.FULL_CONTROL)
    request = MCPToolRequest(
        tool_name="get_status",
        target="lab-a",
        session_id="s1",
        requester_id="agent-1",
        provider="pikvm",
    )

    result = router.handle_tool_request(request)

    assert result.status == MCPResultStatus.VALIDATION_ERROR
    assert result.reason == "unknown MCP provider"
    assert control_plane.handled_requests == []
    assert provider.requests == []
    assert len(sink.events) == 1
