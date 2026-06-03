from agentickvm.control_plane import (
    Actor,
    ActorType,
    AuditEventType,
    CapabilityPolicy,
    CapabilityRequest,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    InMemoryAuditSink,
    PolicyDecision,
    PolicyRule,
    mode_preset,
)
from agentickvm.providers import MockProvider


def _request(capability_id: str, *, target_id: str = "lab-a") -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability_id,
        target_id=target_id,
        session_id="s1",
        correlation_id=f"corr-{capability_id}",
        requester=Actor(type=ActorType.AGENT, id="agent-1"),
        intended_effect="test request",
        parameters={"password": "must-redact"},
    )


def _event_types(sink: InMemoryAuditSink) -> list[str]:
    return [event.event_type.value for event in sink.events]


def test_allowed_request_reaches_mock_provider_after_policy() -> None:
    sink = InMemoryAuditSink()
    provider = MockProvider()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.FULL_CONTROL),
        provider=provider,
        audit_sink=sink,
    )

    result = engine.handle(_request("observe.status"))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.decision.decision == PolicyDecision.ALLOW
    assert result.provider_result is not None
    assert result.provider_result.performed_on_hardware is False
    assert len(provider.requests) == 1
    assert _event_types(sink) == [
        "request_received",
        "capability_resolved",
        "policy_decision",
        "provider_execution_started",
        "provider_execution_completed",
        "result_returned",
    ]
    assert sink.events[0].to_dict()["request"]["parameters"]["password"] == "[REDACTED]"


def test_full_control_can_execute_mock_destructive_action_without_hardware() -> None:
    sink = InMemoryAuditSink()
    provider = MockProvider()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.FULL_CONTROL),
        provider=provider,
        audit_sink=sink,
    )

    result = engine.handle(_request("storage.wipe_disk"))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    assert result.provider_result.performed_on_hardware is False
    assert result.provider_result.data["destructive_effect_simulated"] is True


def test_supervised_dangerous_action_returns_approval_without_provider_call() -> None:
    sink = InMemoryAuditSink()
    provider = MockProvider()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=provider,
        audit_sink=sink,
    )

    result = engine.handle(_request("power.force_off"))

    assert result.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert result.approval_request is not None
    assert result.approval_request.capability.id == "power.force_off"
    assert provider.requests == []
    assert "approval_requested" in _event_types(sink)


def test_unknown_capability_denies_without_provider_call() -> None:
    sink = InMemoryAuditSink()
    provider = MockProvider()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.FULL_CONTROL),
        provider=provider,
        audit_sink=sink,
    )

    result = engine.handle(_request("provider.raw_reset"))

    assert result.status == ControlPlaneStatus.DENIED
    assert result.decision.reason == "unknown capability"
    assert provider.requests == []
    assert "capability_unknown_denied" in _event_types(sink)


def test_custom_policy_can_allow_mock_runtime_noop() -> None:
    sink = InMemoryAuditSink()
    provider = MockProvider()
    policy = CapabilityPolicy(
        name="custom",
        mode=ControlMode.CUSTOM,
        rules={
            "runtime.noop": PolicyRule(decision=PolicyDecision.ALLOW)
        },
    )
    engine = ControlPlane(policy=policy, provider=provider, audit_sink=sink)

    result = engine.handle(_request("runtime.noop"))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert len(provider.requests) == 1
