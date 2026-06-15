import inspect
import json
import stat
from datetime import UTC, datetime, timedelta

import agentickvm.cli.main as cli_module
from agentickvm.cli import main
from agentickvm.control_plane import SignedApprovalCache


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


def test_cli_status_reports_local_operator_console_state(tmp_path, capsys) -> None:
    approval_path = tmp_path / "approvals.json"
    audit_path = tmp_path / "audit.jsonl"
    _run(
        [
            "--approval-path",
            str(approval_path),
            "--audit-path",
            str(audit_path),
            "call",
            "--target",
            "mock-host",
            "--tool",
            "force_restart",
        ],
        capsys,
    )

    exit_code, payload = _run(
        [
            "--approval-path",
            str(approval_path),
            "--audit-path",
            str(audit_path),
            "status",
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["mode"] == "Supervised"
    assert payload["providers"][0]["id"] == "mock"
    assert payload["targets"][0]["id"] == "mock-host"
    assert len(payload["pending_approvals"]) == 1
    assert payload["audit"]["configured"] is True
    assert payload["audit"]["hash_chain_valid"] is True
    assert payload["safety"]["live_providers_enabled_by_default"] is False
    assert payload["safety"]["network_listener"] is False


def test_cli_broker_watch_reads_signed_cache_only(tmp_path, capsys) -> None:
    cache_path = tmp_path / "signed-approvals.json"

    exit_code, payload = _run(
        ["--broker-cache-path", str(cache_path), "approvals", "watch"],
        capsys,
    )

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["operator_surface"] == "approval_broker_cli"
    assert payload["authority"] == "cache_only_signature_required"
    assert payload["signed_grants"] == []
    assert not cache_path.exists()


def test_cli_broker_allow_requires_explicit_dev_signer(tmp_path, capsys) -> None:
    cache_path = tmp_path / "signed-approvals.json"
    expires_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()

    exit_code, payload = _run(
        [
            "--broker-cache-path",
            str(cache_path),
            "approvals",
            "allow",
            "request-1",
            "--operator-id",
            "operator",
            "--session-id",
            "session",
            "--target",
            "mock-host",
            "--provider",
            "mock",
            "--capability",
            "power.force_restart",
            "--params-fingerprint",
            "abc123",
            "--risk-family",
            "power",
            "--expires-at",
            expires_at,
        ],
        capsys,
    )

    assert exit_code == 2
    assert payload["status"] == "validation_error"
    assert "configured signer" in payload["reason"]
    assert not cache_path.exists()


def test_cli_broker_allow_writes_signed_grant_cache(tmp_path, capsys) -> None:
    cache_path = tmp_path / "signed-approvals.json"
    expires_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()

    exit_code, payload = _run(
        [
            "--broker-cache-path",
            str(cache_path),
            "approvals",
            "allow",
            "request-1",
            "--operator-id",
            "operator",
            "--session-id",
            "session",
            "--target",
            "mock-host",
            "--provider",
            "mock",
            "--capability",
            "power.force_restart",
            "--params-fingerprint",
            "abc123",
            "--risk-family",
            "power",
            "--expires-at",
            expires_at,
            "--dev-signer",
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["status"] == "approval_granted"
    assert payload["operator_surface"] == "approval_broker_cli"
    assert payload["production_authority"] is False
    assert payload["grant"]["request_id"] == "request-1"
    assert payload["grant"]["params_fingerprint"] == "abc123"
    assert stat.S_IMODE(cache_path.stat().st_mode) == 0o600
    grants = SignedApprovalCache(cache_path).read_signed_grants()
    assert len(grants) == 1
    assert grants[0].payload.capability == "power.force_restart"


def test_cli_broker_deny_does_not_create_grant(tmp_path, capsys) -> None:
    cache_path = tmp_path / "signed-approvals.json"

    exit_code, payload = _run(
        [
            "--broker-cache-path",
            str(cache_path),
            "approvals",
            "deny",
            "request-1",
            "--operator-id",
            "operator",
            "--reason",
            "not safe",
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["status"] == "approval_denied"
    assert payload["approval"]["grant_created"] is False
    assert not cache_path.exists()
