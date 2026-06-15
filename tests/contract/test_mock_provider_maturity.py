import inspect

from agentickvm.control_plane import (
    Actor,
    ActorType,
    CapabilityRequest,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    InMemoryAuditSink,
    mode_preset,
)
from agentickvm.providers import MockProvider, ProviderActionRequest
from agentickvm.providers import mock as mock_module


def _provider_request(capability: str, **params) -> ProviderActionRequest:
    return ProviderActionRequest(
        capability=capability,
        action=capability.partition(".")[2],
        target_id="mock-host",
        session_id="s1",
        correlation_id=f"corr-{capability}",
        parameters=params,
    )


def _capability_request(capability: str, **params) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability,
        target_id="mock-host",
        session_id="s1",
        correlation_id=f"corr-{capability}",
        requester=Actor(type=ActorType.AGENT, id="agent-1"),
        intended_effect="mock maturity test",
        parameters=params,
    )


def test_safe_mock_observation_capabilities_work() -> None:
    provider = MockProvider()

    assert provider.execute_authorized(_provider_request("observe.screenshot")).data["screen"]
    assert provider.execute_authorized(_provider_request("observe.power_state")).data[
        "power_state"
    ] == "off"
    assert provider.execute_authorized(_provider_request("observe.hardware_inventory")).data[
        "inventory"
    ]["provider"] == "mock"
    assert provider.execute_authorized(_provider_request("observe.sensors")).data["sensors"]
    assert provider.execute_authorized(_provider_request("observe.event_logs")).data[
        "events"
    ] == []
    assert provider.execute_authorized(_provider_request("observe.boot_status")).data[
        "boot_status"
    ]["phase"] == "mock firmware prompt"


def test_mock_state_transitions_are_deterministic_and_resettable() -> None:
    provider = MockProvider()

    provider.execute_authorized(_provider_request("power.on"))
    provider.execute_authorized(_provider_request("media.mount_approved_iso", image="safe.iso"))
    provider.execute_authorized(_provider_request("boot.override", device="cdrom"))

    assert provider.state.power_state == "on"
    assert provider.state.mounted_media == "safe.iso"
    assert provider.state.boot_override == "cdrom"
    assert provider.requests

    provider.reset()

    assert provider.requests == []
    assert provider.state.power_state == "off"
    assert provider.state.mounted_media is None
    assert provider.state.boot_override is None


def test_dangerous_mock_operations_require_approval_or_deny_before_execution() -> None:
    for capability in {
        "power.power_cycle",
        "storage.wipe_disk",
        "network.change_bmc_ip",
        "bmc.rotate_password",
        "media.mount_arbitrary_iso",
        "boot.override",
    }:
        provider = MockProvider()
        engine = ControlPlane(
            policy=mode_preset(ControlMode.SUPERVISED),
            provider=provider,
            audit_sink=InMemoryAuditSink(),
        )

        result = engine.handle(_capability_request(capability))

        assert result.status == ControlPlaneStatus.APPROVAL_REQUIRED
        assert provider.requests == []


def test_mock_operation_audit_events_are_emitted() -> None:
    provider = MockProvider()
    sink = InMemoryAuditSink()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.FULL_CONTROL),
        provider=provider,
        audit_sink=sink,
    )

    result = engine.handle(_capability_request("power.power_cycle"))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    assert result.provider_result.performed_on_hardware is False
    assert "provider_execution_completed" in [event.event_type.value for event in sink.events]


def test_mock_provider_records_fake_input_events() -> None:
    provider = MockProvider()

    key = provider.execute_authorized(_provider_request("input.keyboard_key", key="Enter"))
    typed = provider.execute_authorized(_provider_request("input.keyboard_type", text="hello"))

    assert key.data["input_events"][0]["parameters"]["key"] == "Enter"
    assert typed.data["input_events"][-1]["parameters"]["text"] == "[REDACTED]"


def test_mock_provider_does_not_import_filesystem_or_network_clients() -> None:
    source = inspect.getsource(mock_module)

    assert "import socket" not in source
    assert "import requests" not in source
    assert "from requests" not in source
    assert "import urllib" not in source
    assert "import http.client" not in source
    assert "open(" not in source
