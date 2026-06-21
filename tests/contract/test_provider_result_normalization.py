import json

from agentickvm.cli import main as cli_main
from agentickvm.config import build_runtime, config_from_mapping
from agentickvm.mcp import MCPRouter, MCPToolRequest
from agentickvm.providers import MockProvider, ProviderActionRequest
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


def _request(capability: str, **params) -> ProviderActionRequest:
    return ProviderActionRequest(
        capability=capability,
        action=capability.partition(".")[2],
        target_id="normalize-target",
        session_id="s1",
        correlation_id=f"corr-{capability}",
        parameters=params,
    )


def _pikvm() -> PiKVMObserveProvider:
    return PiKVMObserveProvider(
        enabled=True,
        client=PiKVMObserveClient(transport=default_pikvm_fake_transport()),
    )


def _redfish() -> RedfishObserveProvider:
    return RedfishObserveProvider(
        enabled=True,
        client=RedfishObserveClient(transport=default_redfish_fake_transport()),
    )


def _assert_normalized_shape(payload: dict, *, provider_type: str, capability: str) -> None:
    assert payload["status"] == "ok"
    assert payload["provider_id"]
    assert payload["provider_type"] == provider_type
    assert payload["target"] == "normalize-target"
    assert payload["capability"] == capability
    assert isinstance(payload["data"], dict)
    assert payload["warnings"] == []
    assert payload["redacted"] is True
    assert payload["error_code"] is None
    assert payload["error_message"] == ""
    assert payload["retryable"] is False
    assert payload["performed_on_hardware"] is False


def test_mock_provider_observe_result_shapes_are_normalized() -> None:
    provider = MockProvider()
    expected_data_keys = {
        "observe.screen": "screen",
        "observe.power_state": "power_state",
        "observe.hardware_inventory": "inventory",
        "observe.sensors": "sensors",
        "observe.event_logs": "events",
        "observe.boot_status": "boot_status",
    }

    for capability, data_key in expected_data_keys.items():
        payload = provider.execute_authorized(_request(capability)).normalized()
        _assert_normalized_shape(payload, provider_type="mock", capability=capability)
        assert data_key in payload["data"]


def test_pikvm_provider_observe_result_shapes_are_normalized() -> None:
    provider = _pikvm()

    for capability, data_key in {
        "observe.screen": "screen",
        "observe.power_state": "power_state",
        "observe.hardware_inventory": "inventory",
        "observe.event_logs": "events",
        "observe.boot_status": "boot_status",
    }.items():
        payload = provider.execute_authorized(_request(capability)).normalized()
        _assert_normalized_shape(payload, provider_type="pikvm", capability=capability)
        assert data_key in payload["data"]


def test_redfish_provider_observe_result_shapes_are_normalized() -> None:
    provider = _redfish()

    for capability, data_key in {
        "observe.power_state": "power_state",
        "observe.hardware_inventory": "inventory",
        "observe.sensors": "sensors",
        "observe.event_logs": "events",
        "observe.boot_status": "boot_status",
    }.items():
        payload = provider.execute_authorized(_request(capability)).normalized()
        _assert_normalized_shape(payload, provider_type="redfish", capability=capability)
        assert data_key in payload["data"]


def test_normalized_provider_result_redacts_secret_like_values() -> None:
    payload = MockProvider().execute_authorized(
        _request("observe.status", password="must-not-leak")
    ).normalized()

    assert payload["data"]["parameters"]["password"] == "[REDACTED]"
    assert "must-not-leak" not in repr(payload)


def test_normalized_provider_error_shape() -> None:
    # input.keyboard_type (HID) is outside the Redfish BMC surface -> unsupported.
    payload = _redfish().execute_authorized(_request("input.keyboard_type")).normalized()

    assert payload["status"] == "error"
    assert payload["provider_type"] == "redfish"
    assert payload["error_code"] == "unsupported_capability"
    assert payload["retryable"] is False
    assert payload["performed_on_hardware"] is False


def _fake_config(provider_type: str) -> dict:
    return {
        "version": "0.1",
        "providers": [
            {
                "id": f"{provider_type}-fixture",
                "type": provider_type,
                "enabled": True,
                "metadata": {"fixture_mode": True},
            }
        ],
        "targets": [
            {
                "id": f"{provider_type}-target",
                "provider": f"{provider_type}-fixture",
                "enabled": True,
                "allowed_modes": ["Observe"],
            }
        ],
        "default_policy": {"mode": "Observe"},
    }


def test_mcp_returns_normalized_provider_result() -> None:
    runtime = build_runtime(config_from_mapping(_fake_config("redfish")))
    router = MCPRouter(
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=runtime.policy,
        audit_sink=runtime.audit_sink,
    )

    result = router.handle_tool_request(
        MCPToolRequest(
            tool_name="get_sensors",
            target="redfish-target",
            session_id="s1",
            requester_id="agent-1",
        )
    )
    provider_result = result.to_dict()["data"]["provider_result"]

    assert provider_result["status"] == "ok"
    assert provider_result["provider_type"] == "redfish"
    assert provider_result["capability"] == "observe.sensors"
    assert provider_result["data"]["sensors"][0]["Name"] == "CPU Temp"


def test_cli_returns_normalized_provider_result(tmp_path, capsys) -> None:
    path = tmp_path / "redfish-fixture.yaml"
    path.write_text(json.dumps(_fake_config("redfish")), encoding="utf-8")

    exit_code = cli_main(
        [
            "--config",
            str(path),
            "call",
            "--target",
            "redfish-target",
            "--tool",
            "get_power_state",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    provider_result = payload["data"]["provider_result"]

    assert exit_code == 0
    assert provider_result["status"] == "ok"
    assert provider_result["provider_type"] == "redfish"
    assert provider_result["capability"] == "observe.power_state"
    assert provider_result["data"]["power_state"] == "On"
