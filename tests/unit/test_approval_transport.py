from __future__ import annotations

import json

import pytest

from agentickvm.cli import main as cli_main
from agentickvm.control_plane import (
    ApprovalGrantScope,
    LocalApprovalRecord,
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


def test_local_approval_queue_records_approval_but_is_not_authority(tmp_path, capsys) -> None:
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

    resumed = _approval_required([*base, *call], capsys)
    assert resumed["approval_queue"]["approval_id"] != approval_id
    assert LocalApprovalQueue(approval_path).get(approval_id).status == LocalApprovalStatus.APPROVED

    second_required = _approval_required([*base, *call], capsys)
    assert second_required["approval_queue"]["approval_id"] not in {
        approval_id,
        resumed["approval_queue"]["approval_id"],
    }
    assert verify_audit_chain(audit_path)
    events = [
        json.loads(line)["event"]["event_type"]
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert "approval_requested" in events
    assert "approval_granted" in events
    assert "approval_consumed" not in events


def test_local_approval_queue_session_scope_does_not_resume_execution(tmp_path, capsys) -> None:
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

    assert first["status"] == "approval_required"
    assert first["approval_queue"]["approval_id"] != approval_id
    assert second["status"] == "approval_required"
    assert second["approval_queue"]["approval_id"] not in {
        approval_id,
        first["approval_queue"]["approval_id"],
    }
    assert LocalApprovalQueue(approval_path).get(approval_id).status == LocalApprovalStatus.APPROVED


def test_local_approval_queue_denial_and_expiry_fail_closed(tmp_path, capsys) -> None:
    approval_path = tmp_path / "approvals.json"
    audit_path = tmp_path / "audit.jsonl"
    base = ["--approval-path", str(approval_path), "--audit-path", str(audit_path)]
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
    events = [
        json.loads(line)["event"]["event_type"]
        for line in audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert "approval_denied" in events
    assert "approval_expired" in events


def test_local_approval_queue_redacts_secret_like_text_and_params(tmp_path, capsys) -> None:
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
            "--param",
            "password=do-not-store",
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
    assert "do-not-store" not in contents
    assert "[redacted]" in contents


def test_local_approval_queue_rejects_unknown_and_non_pending_ids(tmp_path) -> None:
    queue = LocalApprovalQueue(tmp_path / "approvals.json")

    with pytest.raises(ValueError, match="Unknown approval id"):
        queue.approve("missing", operator_id="operator-1")


def test_local_approval_fingerprint_mismatch_fails_closed(tmp_path, capsys) -> None:
    approval_path = tmp_path / "approvals.json"
    base = ["--approval-path", str(approval_path)]
    original_call = [
        "call",
        "--target",
        "mock-host",
        "--tool",
        "force_restart",
        "--param",
        "reason=first",
    ]
    changed_call = [
        "call",
        "--target",
        "mock-host",
        "--tool",
        "force_restart",
        "--param",
        "reason=changed",
    ]
    required = _approval_required([*base, *original_call], capsys)
    approval_id = required["approval_queue"]["approval_id"]
    _run_cli(
        [
            *base,
            "approvals",
            "approve",
            approval_id,
            "--operator-id",
            "operator-1",
        ],
        capsys,
    )

    changed = _approval_required([*base, *changed_call], capsys)

    assert changed["approval_queue"]["approval_id"] != approval_id
    assert LocalApprovalQueue(approval_path).get(approval_id).status == LocalApprovalStatus.APPROVED


def test_local_approval_cannot_grant_hard_invariant_action(tmp_path) -> None:
    queue_path = tmp_path / "approvals.json"
    queue = LocalApprovalQueue(queue_path)
    record = LocalApprovalRecord.from_dict(
        {
            "id": "hard-invariant",
            "status": "pending",
            "created_at": "2026-06-06T00:00:00+00:00",
            "expires_at": "2100-06-07T01:00:00+00:00",
            "session_id": "session-1",
            "target_id": "mock-host",
            "provider_id": "mock",
            "capability_id": "session.disable_audit",
            "params_fingerprint": "abc123",
            "policy_decision": "ask_each_time",
            "operator_message": "fabricated hard invariant",
            "material_risks": ["dangerous action"],
            "request": {},
            "redactions": [],
        }
    )
    queue._save_records({"hard-invariant": record})

    with pytest.raises(ValueError, match="cannot be approval-resumed"):
        queue.approve("hard-invariant", operator_id="operator-1")

    assert queue.get("hard-invariant").status == LocalApprovalStatus.PENDING


def test_malformed_approval_store_fails_closed(tmp_path, capsys) -> None:
    approval_path = tmp_path / "approvals.json"
    approval_path.write_text("{not-json}\n", encoding="utf-8")

    exit_code, payload = _run_cli(
        ["--approval-path", str(approval_path), "approvals", "list"],
        capsys,
    )

    assert exit_code == 2
    assert payload["status"] == "validation_error"
