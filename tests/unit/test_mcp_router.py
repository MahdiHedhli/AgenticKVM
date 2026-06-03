from agentickvm.control_plane import (
    CapabilityRequest,
    ControlMode,
    ControlPlane,
    InMemoryAuditSink,
    TargetDefinition,
    TargetRegistry,
    mode_preset,
)
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest
from agentickvm.providers import (
    MockProvider,
    ProviderEntry,
    ProviderRegistry,
)


class SpyControlPlane(ControlPlane):
    handled_requests: list[CapabilityRequest] = []

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def handle(self, request: CapabilityRequest):
        self.handled_requests.append(request)
        return super().handle(request)


def _router(mode: ControlMode = ControlMode.FULL_CONTROL):
    SpyControlPlane.handled_requests = []
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
        targets=[
            TargetDefinition(
                target_id="lab-a",
                provider_id="mock",
                allowed_modes=frozenset(
                    {
                        ControlMode.OBSERVE,
                        ControlMode.ASSISTED,
                        ControlMode.SUPERVISED,
                        ControlMode.FULL_CONTROL,
                    }
                ),
            )
        ],
    )
    router = MCPRouter(
        provider_registry=provider_registry,
        target_registry=target_registry,
        policy=mode_preset(mode),
        audit_sink=sink,
        control_plane_factory=SpyControlPlane,
    )
    return router, SpyControlPlane.handled_requests, provider, sink, provider_registry, target_registry


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
    router, handled_requests, provider, sink, _provider_registry, _target_registry = _router()

    assert isinstance(router, MCPRouter)
    assert handled_requests == []
    assert sink.events == []


def test_observe_tool_succeeds_through_mock_provider_when_policy_allows() -> None:
    router, handled_requests, provider, sink, _provider_registry, _target_registry = _router(
        ControlMode.FULL_CONTROL
    )

    result = router.handle_tool_request(_request("get_power_state"))
    payload = result.to_dict()

    assert result.status == MCPResultStatus.OK
    assert payload["capability"] == "observe.power_state"
    assert payload["provider"] == "mock"
    assert handled_requests[0].capability_id == "observe.power_state"
    assert provider.requests[0].capability == "observe.power_state"
    assert any(event.event_type.value == "provider_execution_completed" for event in sink.events)


def test_unknown_tool_fails_closed_without_provider_call() -> None:
    router, handled_requests, provider, sink, _provider_registry, _target_registry = _router(
        ControlMode.FULL_CONTROL
    )

    result = router.handle_tool_request(_request("provider_raw_reset"))

    assert result.status == MCPResultStatus.VALIDATION_ERROR
    assert result.reason == "unknown MCP tool"
    assert handled_requests == []
    assert provider.requests == []
    assert len(sink.events) == 1


def test_dangerous_tool_returns_approval_required_under_supervised_policy() -> None:
    router, handled_requests, provider, _sink, _provider_registry, _target_registry = _router(
        ControlMode.SUPERVISED
    )

    result = router.handle_tool_request(_request("force_restart"))

    assert result.status == MCPResultStatus.APPROVAL_REQUIRED
    assert result.capability == "power.force_restart"
    assert result.approval_request_id is not None
    assert "dangerous action" in result.risks
    assert handled_requests[0].capability_id == "power.force_restart"
    assert provider.requests == []


def test_approval_required_result_redacts_params_preview() -> None:
    router, _handled_requests, provider, _sink, _provider_registry, _target_registry = _router(
        ControlMode.SUPERVISED
    )

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
    router, _handled_requests, provider, _sink, _provider_registry, _target_registry = _router(
        ControlMode.SUPERVISED
    )
    request = _request("force_restart")

    result = router.handle_tool_request(request)

    assert result.status == MCPResultStatus.APPROVAL_REQUIRED
    assert provider.requests == []


def test_provider_mismatch_fails_closed() -> None:
    router, handled_requests, provider, sink, _provider_registry, _target_registry = _router(
        ControlMode.FULL_CONTROL
    )
    request = MCPToolRequest(
        tool_name="get_status",
        target="lab-a",
        session_id="s1",
        requester_id="agent-1",
        provider="pikvm",
    )

    result = router.handle_tool_request(request)

    assert result.status == MCPResultStatus.VALIDATION_ERROR
    assert result.reason == "Target lab-a is configured for provider mock"
    assert handled_requests == []
    assert provider.requests == []
    assert len(sink.events) == 1


def test_unknown_target_fails_closed() -> None:
    router, handled_requests, provider, sink, _provider_registry, _target_registry = _router(
        ControlMode.FULL_CONTROL
    )
    request = MCPToolRequest(
        tool_name="get_status",
        target="missing",
        session_id="s1",
        requester_id="agent-1",
    )

    result = router.handle_tool_request(request)

    assert result.status == MCPResultStatus.VALIDATION_ERROR
    assert result.reason == "Unknown target id: missing"
    assert handled_requests == []
    assert provider.requests == []
    assert len(sink.events) == 1


def test_disabled_provider_cannot_execute_through_mcp() -> None:
    sink = InMemoryAuditSink()
    provider = MockProvider()
    provider_registry = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                enabled=False,
                provider=provider,
            )
        ]
    )
    target_registry = TargetRegistry(
        provider_registry=provider_registry,
        targets=[TargetDefinition(target_id="lab-a", provider_id="mock")],
    )
    router = MCPRouter(
        provider_registry=provider_registry,
        target_registry=target_registry,
        policy=mode_preset(ControlMode.FULL_CONTROL),
        audit_sink=sink,
        control_plane_factory=SpyControlPlane,
    )

    result = router.handle_tool_request(_request("get_status"))

    assert result.status == MCPResultStatus.VALIDATION_ERROR
    assert result.reason == "Target lab-a references non-executable provider mock"
    assert provider.requests == []


def test_disabled_target_cannot_execute_through_mcp() -> None:
    sink = InMemoryAuditSink()
    provider = MockProvider()
    provider_registry = ProviderRegistry(
        [ProviderEntry(provider_id="mock", provider_type="mock", provider=provider)]
    )
    target_registry = TargetRegistry(
        provider_registry=provider_registry,
        targets=[
            TargetDefinition(
                target_id="lab-a",
                provider_id="mock",
                enabled=False,
            )
        ],
    )
    router = MCPRouter(
        provider_registry=provider_registry,
        target_registry=target_registry,
        policy=mode_preset(ControlMode.FULL_CONTROL),
        audit_sink=sink,
        control_plane_factory=SpyControlPlane,
    )

    result = router.handle_tool_request(_request("get_status"))

    assert result.status == MCPResultStatus.VALIDATION_ERROR
    assert result.reason == "Target is disabled: lab-a"
    assert provider.requests == []
