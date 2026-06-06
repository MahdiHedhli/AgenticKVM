from __future__ import annotations

import json

import pytest

from agentickvm.cli import main as cli_main
from agentickvm.control_plane import (
    ApprovalGrantScope,
    LocalApprovalQueue,
    LocalApprovalStatus,
    verify_audit_chain,
)


def _run_cli(argv, capsys):
    exit_code = cli_main(argv)
    output = capsys.readouterr().out
    return exit_code, json.loads(output)


def _approval_required(cli_args, capsys):
    exit_code, payload = _run_cli(cli_args, capsys)
    assert exit_code == 0
    assert payload["status"] == "approval_required"
    return payload


def test_local_approval_queue_grants_and_consumes_one_time_mock_action(tmp_path, capsys) -> None:
    approval_path = tmp_path / "approvals.json"
    audit_path = tmp_path / "audit.jsonl"
    base = [
        "--approval-path",
        str(approval_path),
        "--audit-path",
        str(audit_path),
    ]
    call = [
        "call",
        "--target",
        "mock-host",
        "--tool",
        "force_restart",
        "--session-id",
        "operator-session",
        "--param",
        "reason=maintenance",
    ]

    required = _approval_required([*base, *call], capsys)
    approval_id = required["approval_queue"]["approval_id"]
    assert LocalApprovalQueue(approval_path).get(approval_id).status == LocalApprovalStatus.PENDING

    exit_code, granted = _run_cli(
        [
            *base,
            "approvals",
            "approve",
            approval_id,
            "--operator-id",
            "operator-1",
            "--reason",
            "approved for test",
        ],
        capsys,
    )
    assert exit_code == 0
    assert granted["status"] == "approval_granted"

    exit_code, resumed = _run_cli([*base, *call], capsys)
    assert exit_code == 0
    assert resumed["status"] == "ok"
    assert resumed["approval_queue"]["status"] == "consumed"

    second_required = _approval_required([*base, *call], capsys)
    assert second_required["approval_queue"]["approval_id"] != approval_id
    assert verify_audit_chain(audit_path)
    events = [
        json.loads(line)["event"]["event_type"]
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert "approval_requested" in events
    assert "approval_granted" in events
    assert "approval_consumed" in events


def test_local_approval_queue_session_scope_remains_reusable(tmp_path, capsys) -> None:
    approval_path = tmp_path / "approvals.json"
    base = ["--approval-path", str(approval_path)]
    call = [
        "call",
        "--target",
        "mock-host",
        "--tool",
        "force_restart",
        "--session-id",
        "operator-session",
        "--param",
        "reason=session",
    ]

    required = _approval_required([*base, *call], capsys)
    approval_id = required["approval_queue"]["approval_id"]
    exit_code, granted = _run_cli(
        [
            *base,
            "approvals",
            "approve",
            approval_id,
            "--operator-id",
            "operator-1",
            "--scope",
            ApprovalGrantScope.SESSION.value,
        ],
        capsys,
    )
    assert exit_code == 0
    assert granted["status"] == "approval_granted"

    first = _run_cli([*base, *call], capsys)[1]
    second = _run_cli([*base, *call], capsys)[1]

    assert first["status"] == "ok"
    assert "approval_queue" not in first
    assert second["status"] == "ok"
    assert LocalApprovalQueue(approval_path).get(approval_id).status == LocalApprovalStatus.APPROVED


def test_local_approval_queue_denial_and_expiry_fail_closed(tmp_path, capsys) -> None:
    approval_path = tmp_path / "approvals.json"
    base = ["--approval-path", str(approval_path)]
    call = [
        "call",
        "--target",
        "mock-host",
        "--tool",
        "force_restart",
        "--param",
        "reason=blocked",
    ]

    denied_required = _approval_required([*base, *call], capsys)
    denied_id = denied_required["approval_queue"]["approval_id"]
    _run_cli(
        [
            *base,
            "approvals",
            "deny",
            denied_id,
            "--operator-id",
            "operator-1",
            "--reason",
            "do not proceed",
        ],
        capsys,
    )
    after_denial = _approval_required([*base, *call], capsys)
    assert after_denial["approval_queue"]["approval_id"] != denied_id

    expired_id = after_denial["approval_queue"]["approval_id"]
    _run_cli(
        [
            *base,
            "approvals",
            "expire",
            expired_id,
            "--operator-id",
            "operator-1",
            "--reason",
            "window closed",
        ],
        capsys,
    )
    after_expiry = _approval_required([*base, *call], capsys)
    assert after_expiry["approval_queue"]["approval_id"] not in {denied_id, expired_id}


def test_local_approval_queue_redacts_secret_like_text(tmp_path, capsys) -> None:
    approval_path = tmp_path / "approvals.json"
    base = ["--approval-path", str(approval_path)]
    required = _approval_required(
        [
            *base,
            "call",
            "--target",
            "mock-host",
            "--tool",
            "force_restart",
            "--param",
            "reason=redaction",
        ],
        capsys,
    )
    approval_id = required["approval_queue"]["approval_id"]

    exit_code, granted = _run_cli(
        [
            *base,
            "approvals",
            "approve",
            approval_id,
            "--operator-id",
            "operator-1",
            "--reason",
            "password secret token",
        ],
        capsys,
    )

    assert exit_code == 0
    assert granted["status"] == "approval_granted"
    contents = approval_path.read_text(encoding="utf-8").lower()
    assert "password secret token" not in contents
    assert "[redacted]" in contents


def test_local_approval_queue_rejects_unknown_and_non_pending_ids(tmp_path) -> None:
    queue = LocalApprovalQueue(tmp_path / "approvals.json")

    with pytest.raises(ValueError, match="Unknown approval id"):
        queue.approve("missing", operator_id="operator-1")
