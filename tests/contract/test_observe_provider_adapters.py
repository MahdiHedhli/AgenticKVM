from agentickvm.control_plane import (
    Actor,
    ActorType,
    CapabilityRequest,
    ControlMode,
    ControlPlane,
    InMemoryAuditSink,
    mode_preset,
)
from agentickvm.providers import ProviderActionRequest, ProviderEntry, ProviderRegistry
from agentickvm.providers.pikvm import (
    PiKVMObserveClient,
    PiKVMObserveProvider,
    default_pikvm_fake_transport,
)
from agentickvm.providers.redfish import (
    RedfishObserveClient,
    RedfishObserveProvider,
    default_redfish_fake_transport,
)


def _provider_request(capability: str) -> ProviderActionRequest:
    return ProviderActionRequest(
        capability=capability,
        action=capability.partition(".")[2],
        target_id="fixture-target",
        session_id="s1",
        correlation_id=f"corr-{capability}",
    )


def _capability_request(capability: str, target_id: str) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability,
        target_id=target_id,
        session_id="s1",
        correlation_id=f"corr-{target_id}-{capability}",
        requester=Actor(type=ActorType.AGENT, id="agent-1"),
        intended_effect=f"test {capability}",
    )


def test_pikvm_observe_provider_is_disabled_by_default() -> None:
    provider = PiKVMObserveProvider()

    assert provider.enabled is False
    assert provider.is_real_hardware is True
    assert provider.status().risk_class == "real_hardware_disabled"
    result = provider.execute_authorized(_provider_request("observe.status"))
    assert result.ok is False
    assert result.performed_on_hardware is False


def test_redfish_observe_provider_is_disabled_by_default() -> None:
    provider = RedfishObserveProvider()

    assert provider.enabled is False
    assert provider.is_real_hardware is True
    assert provider.status().risk_class == "real_hardware_disabled"
    result = provider.execute_authorized(_provider_request("observe.power_state"))
    assert result.ok is False
    assert result.performed_on_hardware is False


def test_pikvm_fake_provider_executes_observe_only() -> None:
    provider = PiKVMObserveProvider(
        provider_id="pikvm-fixture",
        enabled=True,
        client=PiKVMObserveClient(transport=default_pikvm_fake_transport()),
    )

    result = provider.execute_authorized(_provider_request("observe.screenshot"))

    assert result.ok is True
    assert result.performed_on_hardware is False
    assert result.data["fixture"] is True
    assert result.data["screen"]["content"] == "[REDACTED]"


def test_redfish_fake_provider_executes_observe_only() -> None:
    provider = RedfishObserveProvider(
        provider_id="redfish-fixture",
        enabled=True,
        client=RedfishObserveClient(transport=default_redfish_fake_transport()),
    )

    result = provider.execute_authorized(_provider_request("observe.sensors"))

    assert result.ok is True
    assert result.performed_on_hardware is False
    assert result.data["fixture"] is True
    assert result.data["sensors"][0]["Name"] == "CPU Temp"


def test_out_of_surface_capability_is_unsupported_by_fixture_providers() -> None:
    pikvm = PiKVMObserveProvider(
        enabled=True,
        client=PiKVMObserveClient(transport=default_pikvm_fake_transport()),
    )
    redfish = RedfishObserveProvider(
        enabled=True,
        client=RedfishObserveClient(transport=default_redfish_fake_transport()),
    )

    # bmc.rotate_password is outside both fixture providers' supported surfaces.
    for provider in (pikvm, redfish):
        result = provider.execute_authorized(_provider_request("bmc.rotate_password"))
        assert result.ok is False
        assert result.performed_on_hardware is False
        assert "unsupported" in result.message.lower()


def test_provider_registry_can_register_explicit_fixture_provider() -> None:
    provider = RedfishObserveProvider(
        provider_id="redfish-fixture",
        enabled=True,
        client=RedfishObserveClient(transport=default_redfish_fake_transport()),
    )
    registry = ProviderRegistry(
        [ProviderEntry(provider_id="redfish-fixture", provider_type="redfish", provider=provider)]
    )

    resolved = registry.resolve_enabled("redfish-fixture")

    assert resolved is provider
    assert registry.list_summaries()[0]["executable"] is True


def test_observe_provider_execution_audits_through_control_plane() -> None:
    provider = RedfishObserveProvider(
        provider_id="redfish-fixture",
        enabled=True,
        client=RedfishObserveClient(transport=default_redfish_fake_transport()),
    )
    sink = InMemoryAuditSink()
    control_plane = ControlPlane(
        policy=mode_preset(ControlMode.OBSERVE),
        provider=provider,
        audit_sink=sink,
    )

    result = control_plane.handle(
        _capability_request("observe.power_state", "redfish-target")
    )

    assert result.status.value == "completed"
    assert result.provider_result is not None
    assert result.provider_result.performed_on_hardware is False
    assert any(event.event_type.value == "provider_execution_completed" for event in sink.events)
