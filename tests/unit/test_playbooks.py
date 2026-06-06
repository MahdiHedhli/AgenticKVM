from __future__ import annotations

import inspect
import json

from agentickvm.cli import main as cli_main
import agentickvm.playbooks as playbooks_module
from agentickvm.config import build_runtime, mock_only_config
from agentickvm.playbooks import PlaybookRunner


def _run_cli(argv, capsys):
    exit_code = cli_main(argv)
    output = capsys.readouterr().out
    return exit_code, json.loads(output)


def test_playbook_registry_lists_safe_defaults() -> None:
    runner = PlaybookRunner(build_runtime(mock_only_config()))

    payload = runner.list_playbooks()
    names = {playbook["name"] for playbook in payload["playbooks"]}

    assert payload["status"] == "ok"
    assert "observe-target-health" in names
    assert "capture-screen-evidence" in names
    assert "collect-pre-recovery-evidence" in names


def test_playbook_dry_run_does_not_execute_provider() -> None:
    runtime = build_runtime(mock_only_config())
    runner = PlaybookRunner(runtime)
    provider = runtime.provider_registry.resolve_enabled("mock")

    payload = runner.dry_run("observe-target-health", target="mock-host")

    assert payload["status"] == "dry_run"
    assert payload["would_execute"] is False
    assert provider.requests == []


def test_playbook_run_routes_mock_observe_through_control_plane() -> None:
    runtime = build_runtime(mock_only_config())
    runner = PlaybookRunner(runtime)
    provider = runtime.provider_registry.resolve_enabled("mock")

    payload = runner.run("observe-target-health", target="mock-host")

    assert payload["status"] == "ok"
    assert [item["result"]["status"] for item in payload["results"]] == ["ok", "ok"]
    assert len(provider.requests) == 2


def test_playbook_run_fails_closed_for_unknown_target() -> None:
    runner = PlaybookRunner(build_runtime(mock_only_config()))

    payload = runner.run("observe-target-health", target="missing")

    assert payload["status"] == "stopped"
    assert payload["stop_status"] == "validation_error"


def test_playbooks_do_not_call_providers_directly() -> None:
    source = inspect.getsource(playbooks_module)

    assert "execute_authorized" not in source
    assert "MockProvider" not in source


def test_cli_playbook_list_dry_run_and_run(capsys) -> None:
    list_exit, listed = _run_cli(["playbooks", "list"], capsys)
    dry_exit, dry = _run_cli(
        ["playbooks", "dry-run", "observe-target-health", "--target", "mock-host"],
        capsys,
    )
    run_exit, run = _run_cli(
        ["playbooks", "run", "observe-target-health", "--target", "mock-host"],
        capsys,
    )

    assert list_exit == 0
    assert listed["status"] == "ok"
    assert dry_exit == 0
    assert dry["status"] == "dry_run"
    assert run_exit == 0
    assert run["status"] == "ok"


def test_cli_playbook_run_uses_audit_path(tmp_path, capsys) -> None:
    audit_path = tmp_path / "playbook-audit.jsonl"

    exit_code, payload = _run_cli(
        [
            "--audit-path",
            str(audit_path),
            "playbooks",
            "run",
            "observe-target-health",
            "--target",
            "mock-host",
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert audit_path.exists()
    assert "provider_execution_completed" in audit_path.read_text(encoding="utf-8")
