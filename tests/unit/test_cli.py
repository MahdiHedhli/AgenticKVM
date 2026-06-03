import inspect
import json

import agentickvm.cli.main as cli_module
from agentickvm.cli import main


def _run(argv, capsys):
    exit_code = main(argv)
    output = capsys.readouterr().out
    return exit_code, json.loads(output)


def test_cli_imports() -> None:
    assert callable(main)


def test_cli_lists_mock_providers_by_default(capsys) -> None:
    exit_code, payload = _run(["list-providers"], capsys)

    assert exit_code == 0
    assert payload["providers"] == [
        {
            "id": "mock",
            "type": "mock",
            "enabled": True,
            "executable": True,
            "description": "Safe in-memory mock provider",
        }
    ]


def test_cli_lists_mock_targets_by_default(capsys) -> None:
    exit_code, payload = _run(["list-targets"], capsys)

    assert exit_code == 0
    assert payload["targets"][0]["id"] == "mock-host"
    assert payload["targets"][0]["provider"] == "mock"
    assert payload["targets"][0]["enabled"] is True


def test_cli_observe_mock_target_succeeds(capsys) -> None:
    exit_code, payload = _run(
        ["call", "--target", "mock-host", "--tool", "get_power_state"],
        capsys,
    )

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["capability"] == "observe.power_state"
    assert payload["provider"] == "mock"


def test_cli_dangerous_action_returns_approval_required(capsys) -> None:
    exit_code, payload = _run(
        ["call", "--target", "mock-host", "--tool", "force_restart"],
        capsys,
    )

    assert exit_code == 0
    assert payload["status"] == "approval_required"
    assert payload["capability"] == "power.force_restart"
    assert "dangerous action" in payload["risks"]


def test_cli_unknown_target_fails_closed(capsys) -> None:
    exit_code, payload = _run(
        ["call", "--target", "missing", "--tool", "get_power_state"],
        capsys,
    )

    assert exit_code == 2
    assert payload["status"] == "validation_error"
    assert payload["reason"] == "Unknown target id: missing"


def test_cli_unknown_tool_fails_closed(capsys) -> None:
    exit_code, payload = _run(
        ["call", "--target", "mock-host", "--tool", "provider_raw_reset"],
        capsys,
    )

    assert exit_code == 2
    assert payload["status"] == "validation_error"
    assert payload["reason"] == "unknown MCP tool"


def test_cli_does_not_call_providers_directly() -> None:
    source = inspect.getsource(cli_module)

    assert "execute_authorized" not in source
    assert "MockProvider" not in source


def test_cli_does_not_require_secrets(monkeypatch, capsys) -> None:
    monkeypatch.delenv("AGENTICKVM_TOKEN", raising=False)
    monkeypatch.delenv("AGENTICKVM_PASSWORD", raising=False)

    exit_code, payload = _run(["list-providers"], capsys)

    assert exit_code == 0
    assert payload["providers"][0]["id"] == "mock"
