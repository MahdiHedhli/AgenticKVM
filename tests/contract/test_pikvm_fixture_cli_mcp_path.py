import inspect
import json
from pathlib import Path

import agentickvm.cli.main as cli_module
import agentickvm.mcp.router as router_module
from agentickvm.cli import main as cli_main
from agentickvm.config import build_runtime, load_config
from agentickvm.control_plane import CapabilityRequest, ControlPlane
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest
from agentickvm.providers.pikvm import PiKVMObserveProvider
from agentickvm.providers.pikvm_transport import FakePiKVMObserveTransport

ROOT = Path(__file__).resolve().parents[2]
PIKVM_FIXTURE_CONFIG = ROOT / "examples" / "config" / "pikvm-observe-fixture.yaml"


class SpyControlPlane(ControlPlane):
    handled: list[CapabilityRequest] = []

    def handle(self, request: CapabilityRequest):
        self.handled.append(request)
        return super().handle(request)


def _run_cli(argv, capsys):
    exit_code = cli_main(argv)
    output = capsys.readouterr().out
    return exit_code, json.loads(output)


def _runtime():
    return build_runtime(load_config(PIKVM_FIXTURE_CONFIG))


def _router():
    SpyControlPlane.handled = []
    runtime = _runtime()
    router = MCPRouter(
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=runtime.policy,
        audit_sink=runtime.audit_sink,
        control_plane_factory=SpyControlPlane,
    )
    provider = runtime.provider_registry.resolve_enabled("pikvm-fixture")
    return router, provider


def _request(tool_name: str) -> MCPToolRequest:
    return MCPToolRequest(
        tool_name=tool_name,
        target="pikvm-fixture-target",
        session_id="s1",
        requester_id="agent-1",
        provider="pikvm-fixture",
        correlation_id=f"pikvm-fixture-{tool_name}",
    )


def test_cli_lists_pikvm_fixture_provider_and_target(capsys) -> None:
    providers_code, providers = _run_cli(
        ["--config", str(PIKVM_FIXTURE_CONFIG), "list-providers"],
        capsys,
    )
    targets_code, targets = _run_cli(
        ["--config", str(PIKVM_FIXTURE_CONFIG), "list-targets"],
        capsys,
    )

    assert providers_code == 0
    assert providers["providers"][0]["id"] == "pikvm-fixture"
    assert providers["providers"][0]["type"] == "pikvm"
    assert providers["providers"][0]["executable"] is True
    assert "credential_ref" not in repr(providers)
    assert targets_code == 0
    assert targets["targets"][0]["id"] == "pikvm-fixture-target"
    assert targets["targets"][0]["allowed_modes"] == ["Observe"]


def test_cli_pikvm_fixture_observe_screen_and_power_state(capsys) -> None:
    screen_code, screen = _run_cli(
        [
            "--config",
            str(PIKVM_FIXTURE_CONFIG),
            "call",
            "--target",
            "pikvm-fixture-target",
            "--tool",
            "observe_screen",
        ],
        capsys,
    )
    power_code, power = _run_cli(
        [
            "--config",
            str(PIKVM_FIXTURE_CONFIG),
            "call",
            "--target",
            "pikvm-fixture-target",
            "--tool",
            "get_power_state",
        ],
        capsys,
    )

    assert screen_code == 0
    assert screen["status"] == "ok"
    assert (
        screen["data"]["provider_result"]["data"]["screen"]["content"]
        == "[REDACTED]"
    )
    assert screen["data"]["provider_result"]["data"]["screenshot"]["raw_bytes_included"] is False
    assert "keychain://" not in repr(screen)
    assert power_code == 0
    assert power["status"] == "ok"
    assert power["data"]["provider_result"]["data"]["power_state"] == "on"


def test_cli_pikvm_fixture_mutating_tool_fails_closed(capsys) -> None:
    exit_code, payload = _run_cli(
        [
            "--config",
            str(PIKVM_FIXTURE_CONFIG),
            "call",
            "--target",
            "pikvm-fixture-target",
            "--tool",
            "power_on",
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["status"] == "denied"
    assert payload["capability"] == "power.on"


def test_mcp_pikvm_fixture_observe_screen_uses_control_plane_and_fake_transport() -> None:
    router, provider = _router()

    result = router.handle_tool_request(_request("observe_screen"))

    assert isinstance(provider, PiKVMObserveProvider)
    assert isinstance(provider.client.observe_transport, FakePiKVMObserveTransport)
    assert result.status == MCPResultStatus.OK
    assert SpyControlPlane.handled[0].capability_id == "observe.screenshot"
    assert provider.requests[0].capability == "observe.screenshot"
    assert provider.client.transport is not None
    assert all(call.method == "GET" for call in provider.client.transport.calls)


def test_mcp_pikvm_fixture_mutating_tool_denies_before_provider_execution() -> None:
    router, provider = _router()

    result = router.handle_tool_request(_request("power_on"))

    assert result.status == MCPResultStatus.DENIED
    assert result.capability == "power.on"
    assert provider.requests == []


def test_mcp_pikvm_fixture_provider_mismatch_fails_closed() -> None:
    router, provider = _router()

    result = router.handle_tool_request(
        MCPToolRequest(
            tool_name="observe_screen",
            target="pikvm-fixture-target",
            session_id="s1",
            requester_id="agent-1",
            provider="other-provider",
        )
    )

    assert result.status == MCPResultStatus.VALIDATION_ERROR
    assert provider.requests == []
    assert "configured for provider pikvm-fixture" in result.reason


def test_cli_mcp_pikvm_fixture_path_has_no_direct_provider_calls() -> None:
    cli_source = inspect.getsource(cli_module)
    router_source = inspect.getsource(router_module)

    assert "execute_authorized" not in cli_source
    assert "execute_authorized" not in router_source
    assert "PiKVMObserveProvider(" not in cli_source
    assert "PiKVMObserveProvider(" not in router_source
