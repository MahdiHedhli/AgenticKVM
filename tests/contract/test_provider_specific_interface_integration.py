import inspect
import json

import agentickvm.cli.main as cli_module
import agentickvm.mcp.router as router_module
from agentickvm.cli import main as cli_main
from agentickvm.config import build_runtime, config_from_mapping, load_config
from agentickvm.control_plane import CapabilityRequest, ControlPlane
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest
from agentickvm.providers.pikvm import PiKVMObserveProvider
from agentickvm.providers.redfish import RedfishObserveProvider


class SpyControlPlane(ControlPlane):
    handled: list[CapabilityRequest] = []

    def handle(self, request: CapabilityRequest):
        self.handled.append(request)
        return super().handle(request)


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


def _router(provider_type: str) -> tuple[MCPRouter, object]:
    SpyControlPlane.handled = []
    runtime = build_runtime(config_from_mapping(_fake_config(provider_type)))
    provider = runtime.provider_registry.resolve_enabled(f"{provider_type}-fixture")
    router = MCPRouter(
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=runtime.policy,
        audit_sink=runtime.audit_sink,
        control_plane_factory=SpyControlPlane,
    )
    return router, provider


def _request(provider_type: str, tool_name: str) -> MCPToolRequest:
    return MCPToolRequest(
        tool_name=tool_name,
        target=f"{provider_type}-target",
        session_id="s1",
        requester_id="agent-1",
        provider=f"{provider_type}-fixture",
        correlation_id=f"corr-{provider_type}-{tool_name}",
    )


def _write_config(tmp_path, provider_type: str):
    path = tmp_path / f"{provider_type}-fixture.yaml"
    path.write_text(json.dumps(_fake_config(provider_type)), encoding="utf-8")
    return path


def _run_cli(argv, capsys):
    exit_code = cli_main(argv)
    output = capsys.readouterr().out
    return exit_code, json.loads(output)


def test_mcp_observes_redfish_fake_target_power_state_and_sensors() -> None:
    router, provider = _router("redfish")

    power = router.handle_tool_request(_request("redfish", "get_power_state"))
    sensors = router.handle_tool_request(_request("redfish", "get_sensors"))

    assert isinstance(provider, RedfishObserveProvider)
    assert power.status == MCPResultStatus.OK
    assert power.data["provider_result"]["data"]["power_state"] == "On"
    assert sensors.status == MCPResultStatus.OK
    assert sensors.data["provider_result"]["data"]["sensors"][0]["Name"] == "CPU Temp"
    assert [request.capability_id for request in SpyControlPlane.handled] == [
        "observe.power_state",
        "observe.sensors",
    ]
    assert [request.capability for request in provider.requests] == [
        "observe.power_state",
        "observe.sensors",
    ]


def test_mcp_observes_pikvm_fake_target_screen_and_status() -> None:
    router, provider = _router("pikvm")

    screen = router.handle_tool_request(_request("pikvm", "observe_screen"))
    status = router.handle_tool_request(_request("pikvm", "get_status"))

    assert isinstance(provider, PiKVMObserveProvider)
    assert screen.status == MCPResultStatus.OK
    assert (
        screen.data["provider_result"]["data"]["screen"]["content"]
        == "PiKVM fixture screen"
    )
    assert status.status == MCPResultStatus.OK
    assert status.data["provider_result"]["data"]["status"]["health"] == "ok"
    assert [request.capability_id for request in SpyControlPlane.handled] == [
        "observe.screenshot",
        "observe.status",
    ]


def test_mcp_mutating_tool_against_fake_provider_denies_before_execution() -> None:
    router, provider = _router("redfish")

    result = router.handle_tool_request(_request("redfish", "power_on"))

    assert result.status == MCPResultStatus.DENIED
    assert result.capability == "power.on"
    assert provider.requests == []


def test_mcp_disabled_provider_placeholder_denies() -> None:
    config = config_from_mapping(
        {
            "version": "0.1",
            "providers": [
                {"id": "redfish-disabled", "type": "redfish", "enabled": False}
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
    runtime = build_runtime(config)
    router = MCPRouter(
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=runtime.policy,
        audit_sink=runtime.audit_sink,
    )

    result = router.handle_tool_request(
        MCPToolRequest(
            tool_name="get_power_state",
            target="redfish-target",
            session_id="s1",
            requester_id="agent-1",
        )
    )

    assert result.status == MCPResultStatus.VALIDATION_ERROR
    assert "non-executable provider" in result.reason


def test_cli_lists_fake_providers_and_targets(tmp_path, capsys) -> None:
    path = _write_config(tmp_path, "redfish")

    providers_code, providers = _run_cli(["--config", str(path), "list-providers"], capsys)
    targets_code, targets = _run_cli(["--config", str(path), "list-targets"], capsys)

    assert providers_code == 0
    assert providers["providers"][0]["id"] == "redfish-fixture"
    assert providers["providers"][0]["executable"] is True
    assert "metadata" not in providers["providers"][0]
    assert targets_code == 0
    assert targets["targets"][0]["id"] == "redfish-target"
    assert "metadata" not in targets["targets"][0]


def test_cli_calls_redfish_fake_observe_power_state_and_sensors(tmp_path, capsys) -> None:
    path = _write_config(tmp_path, "redfish")

    power_code, power = _run_cli(
        [
            "--config",
            str(path),
            "call",
            "--target",
            "redfish-target",
            "--tool",
            "get_power_state",
        ],
        capsys,
    )
    sensors_code, sensors = _run_cli(
        [
            "--config",
            str(path),
            "call",
            "--target",
            "redfish-target",
            "--tool",
            "get_sensors",
        ],
        capsys,
    )

    assert power_code == 0
    assert power["status"] == "ok"
    assert power["data"]["provider_result"]["data"]["power_state"] == "On"
    assert sensors_code == 0
    assert sensors["status"] == "ok"
    assert sensors["data"]["provider_result"]["data"]["sensors"][0]["Name"] == "CPU Temp"


def test_cli_calls_pikvm_fake_observe_screen_and_status(tmp_path, capsys) -> None:
    path = _write_config(tmp_path, "pikvm")

    screen_code, screen = _run_cli(
        [
            "--config",
            str(path),
            "call",
            "--target",
            "pikvm-target",
            "--tool",
            "observe_screen",
        ],
        capsys,
    )
    status_code, status = _run_cli(
        [
            "--config",
            str(path),
            "call",
            "--target",
            "pikvm-target",
            "--tool",
            "get_status",
        ],
        capsys,
    )

    assert screen_code == 0
    assert screen["status"] == "ok"
    assert (
        screen["data"]["provider_result"]["data"]["screen"]["content"]
        == "PiKVM fixture screen"
    )
    assert status_code == 0
    assert status["status"] == "ok"
    assert status["data"]["provider_result"]["data"]["status"]["health"] == "ok"


def test_cli_mutating_call_against_fake_provider_denies(tmp_path, capsys) -> None:
    path = _write_config(tmp_path, "redfish")

    exit_code, payload = _run_cli(
        [
            "--config",
            str(path),
            "call",
            "--target",
            "redfish-target",
            "--tool",
            "power_on",
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["status"] == "denied"
    assert payload["capability"] == "power.on"


def test_cli_and_mcp_do_not_call_providers_directly() -> None:
    cli_source = inspect.getsource(cli_module)
    router_source = inspect.getsource(router_module)

    assert "execute_authorized" not in cli_source
    assert "execute_authorized" not in router_source
    assert "PiKVMObserveProvider" not in cli_source
    assert "RedfishObserveProvider" not in cli_source
