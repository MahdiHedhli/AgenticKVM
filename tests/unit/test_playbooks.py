from __future__ import annotations

import inspect
import json

import pytest

from agentickvm.cli import main as cli_main
import agentickvm.playbooks as playbooks_module
from agentickvm.config import build_runtime, mock_only_config
from agentickvm.control_plane import CapabilityPolicy, PolicyRule
from agentickvm.control_plane.decisions import PolicyDecision
from agentickvm.playbooks import (
    PlaybookDefinition,
    PlaybookRegistry,
    PlaybookRunner,
    PlaybookStep,
)


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


def test_playbook_registry_rejects_unknown_tool_and_missing_capability() -> None:
    unknown_tool = PlaybookDefinition(
        name="bad-tool",
        description="bad",
        required_capabilities=("observe.status",),
        risk_tier="low",
        steps=(PlaybookStep("bad", "missing_tool", "bad"),),
    )
    missing_capability = PlaybookDefinition(
        name="bad-capability",
        description="bad",
        required_capabilities=("observe.status",),
        risk_tier="low",
        steps=(PlaybookStep("power", "get_power_state", "power"),),
    )

    with pytest.raises(ValueError, match="unknown tool"):
        PlaybookRegistry((unknown_tool,))
    with pytest.raises(ValueError, match="missing required capability"):
        PlaybookRegistry((missing_capability,))


def test_playbook_approval_required_step_stops_without_auto_approval() -> None:
    dangerous = PlaybookDefinition(
        name="dangerous-test",
        description="dangerous test",
        required_capabilities=("power.force_restart",),
        risk_tier="high",
        rollback_notes="mock-only dangerous step test",
        steps=(PlaybookStep("restart", "force_restart", "restart"),),
    )
    runner = PlaybookRunner(
        build_runtime(mock_only_config()),
        registry=PlaybookRegistry((dangerous,)),
    )

    payload = runner.run("dangerous-test", target="mock-host")

    assert payload["status"] == "stopped"
    assert payload["stop_status"] == "approval_required"


def test_playbook_policy_denial_is_preserved() -> None:
    runtime = build_runtime(mock_only_config())
    runtime = runtime.__class__(
        config=runtime.config,
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=CapabilityPolicy(
            name="deny observe",
            mode="Supervised",
            rules={
                "observe.status": PolicyRule(
                    decision=PolicyDecision.DENY,
                    reason="deny for test",
                )
            },
        ),
        audit_sink=runtime.audit_sink,
        approval_store=runtime.approval_store,
    )
    runner = PlaybookRunner(runtime)

    payload = runner.run("observe-target-health", target="mock-host")

    assert payload["status"] == "stopped"
    assert payload["stop_status"] == "denied"


def test_playbooks_do_not_call_providers_directly() -> None:
    source = inspect.getsource(playbooks_module)

    assert "execute_authorized" not in source
    assert "MockProvider" not in source


def test_playbook_output_redacts_secret_like_params() -> None:
    secret_step = PlaybookDefinition(
        name="redaction-test",
        description="redaction test",
        required_capabilities=("observe.status",),
        risk_tier="low",
        steps=(
            PlaybookStep(
                "status",
                "get_status",
                "status",
                params={"api_key": "do-not-leak"},
            ),
        ),
    )
    runner = PlaybookRunner(
        build_runtime(mock_only_config()),
        registry=PlaybookRegistry((secret_step,)),
    )

    payload = runner.run("redaction-test", target="mock-host")

    encoded = json.dumps(payload).lower()
    assert "do-not-leak" not in encoded
    assert "[redacted]" in encoded


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
