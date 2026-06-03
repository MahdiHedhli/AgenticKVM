from agentickvm.control_plane import (
    Actor,
    ActorType,
    AuditEventType,
    CapabilityRequest,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    InMemoryAuditSink,
    mode_preset,
)
from agentickvm.providers.pikvm import (
    PiKVMObserveClient,
    PiKVMObserveProvider,
    default_pikvm_fake_transport,
)
from agentickvm.providers.pikvm_transport import FakePiKVMObserveTransport


def _request(capability_id: str) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability_id,
        target_id="pikvm-fixture-target",
        session_id="s1",
        correlation_id=f"pikvm-fixture-{capability_id}",
        requester=Actor(type=ActorType.AGENT, id="agent-1"),
        intended_effect=f"observe PiKVM fixture with {capability_id}",
        parameters={"credential_ref": "keychain://agentickvm/example"},
        credential_id="keychain://agentickvm/example",
    )


def _provider() -> PiKVMObserveProvider:
    transport = default_pikvm_fake_transport()
    return PiKVMObserveProvider(
        provider_id="pikvm-fixture",
        enabled=True,
        client=PiKVMObserveClient(
            observe_transport=FakePiKVMObserveTransport(transport=transport)
        ),
    )


def _event_types(sink: InMemoryAuditSink) -> list[AuditEventType]:
    return [event.event_type for event in sink.events]


def test_pikvm_provider_reports_fixture_status_without_live_contact() -> None:
    provider = _provider()

    status = provider.status()

    assert status.enabled is True
    assert status.is_real_hardware is False
    assert status.risk_class == "test_fake_observe_only"
    assert "fixture-backed" in status.message


def test_pikvm_observe_screen_runs_through_control_plane_and_fake_transport() -> None:
    sink = InMemoryAuditSink()
    provider = _provider()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.OBSERVE),
        provider=provider,
        audit_sink=sink,
    )

    result = engine.handle(_request("observe.screen"))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    assert result.provider_result.performed_on_hardware is False
    assert result.provider_result.data["screen"]["content"] == "PiKVM fixture screen"
    assert len(provider.requests) == 1
    assert AuditEventType.PROVIDER_EXECUTION_STARTED in _event_types(sink)
    assert AuditEventType.PROVIDER_EXECUTION_COMPLETED in _event_types(sink)


def test_pikvm_observe_screenshot_returns_metadata_without_raw_bytes() -> None:
    sink = InMemoryAuditSink()
    provider = _provider()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.OBSERVE),
        provider=provider,
        audit_sink=sink,
    )

    result = engine.handle(_request("observe.screenshot"))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    screenshot = result.provider_result.data["screenshot"]
    assert screenshot["raw_bytes_included"] is False
    assert screenshot["artifact"]["target_id"] == "[REDACTED]"
    assert "raw_image" not in repr(result.provider_result.data)
    assert "keychain://agentickvm/example" not in repr(result.provider_result)


def test_pikvm_observe_power_state_runs_through_control_plane() -> None:
    sink = InMemoryAuditSink()
    provider = _provider()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.OBSERVE),
        provider=provider,
        audit_sink=sink,
    )

    result = engine.handle(_request("observe.power_state"))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    assert result.provider_result.data["power_state"] == "on"


def test_pikvm_unsupported_observe_capability_fails_closed_after_policy() -> None:
    sink = InMemoryAuditSink()
    provider = _provider()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.OBSERVE),
        provider=provider,
        audit_sink=sink,
    )

    result = engine.handle(_request("observe.sensors"))

    assert result.status == ControlPlaneStatus.FAILED
    assert result.provider_result is not None
    assert result.provider_result.ok is False
    assert result.provider_result.error_code == "unsupported_capability"
    assert result.provider_result.performed_on_hardware is False
    assert AuditEventType.PROVIDER_EXECUTION_FAILED in _event_types(sink)


def test_disabled_pikvm_provider_still_cannot_execute() -> None:
    provider = PiKVMObserveProvider()
    sink = InMemoryAuditSink()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.OBSERVE),
        provider=provider,
        audit_sink=sink,
    )

    result = engine.handle(_request("observe.screen"))

    assert result.status == ControlPlaneStatus.DENIED
    assert result.provider_result is None
    assert "real hardware provider outside policy scope" in result.message
