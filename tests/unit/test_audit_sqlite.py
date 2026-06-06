from __future__ import annotations

import json
import sqlite3

import pytest

from agentickvm.cli import main as cli_main
from agentickvm.control_plane import (
    SQLiteAuditError,
    create_sqlite_audit_checkpoint,
    export_sqlite_audit,
    inspect_sqlite_audit_event,
    list_sqlite_audit_events,
    verify_sqlite_audit_checkpoint,
    verify_sqlite_audit_chain,
)


def _run_cli(argv, capsys):
    exit_code = cli_main(argv)
    output = capsys.readouterr().out
    return exit_code, json.loads(output)


def test_sqlite_audit_sink_persists_and_verifies_cli_flow(tmp_path, capsys) -> None:
    audit_path = tmp_path / "audit.sqlite"

    exit_code, payload = _run_cli(
        [
            "--audit-sqlite-path",
            str(audit_path),
            "call",
            "--target",
            "mock-host",
            "--tool",
            "get_power_state",
        ],
        capsys,
    )

    assert exit_code == 0
    assert payload["status"] == "ok"
    verification = verify_sqlite_audit_chain(audit_path)
    assert verification.ok is True
    assert verification.event_count > 0
    events = list_sqlite_audit_events(audit_path, limit=10)
    assert events
    assert events[-1]["event"]["event_type"] == "result_returned"

    reopened = verify_sqlite_audit_chain(audit_path)
    assert reopened.ok is True
    assert reopened.event_count == verification.event_count


def test_sqlite_audit_export_and_checkpoint_are_explicit_path_json_safe(
    tmp_path,
    capsys,
) -> None:
    audit_path = tmp_path / "audit.sqlite"
    export_path = tmp_path / "audit-export.json"
    _run_cli(
        [
            "--audit-sqlite-path",
            str(audit_path),
            "call",
            "--target",
            "mock-host",
            "--tool",
            "get_power_state",
        ],
        capsys,
    )
    checkpoint = create_sqlite_audit_checkpoint(
        audit_path,
        audit_log_id="sqlite-test",
        metadata={"operator": "tester", "api_key": "should-redact"},
        checkpoint_id="sqlite-checkpoint-1",
    )

    checkpoint_verification = verify_sqlite_audit_checkpoint(audit_path, checkpoint)
    payload = export_sqlite_audit(
        audit_path,
        output_path=export_path,
        checkpoint=checkpoint,
    )

    assert export_path.exists()
    assert payload["format"] == "agentickvm.sqlite-audit-export.v1"
    assert payload["verification"]["ok"] is True
    assert checkpoint_verification.ok is True
    assert payload["checkpoint_verified"] is True
    assert payload["checkpoint"]["metadata"]["api_key"] == "[REDACTED]"
    lowered = export_path.read_text(encoding="utf-8").lower()
    assert "password" not in lowered
    assert "should-redact" not in lowered
    assert "[redacted]" in lowered
    assert "screenshot_bytes" not in lowered


def test_sqlite_audit_tamper_is_detected(tmp_path, capsys) -> None:
    audit_path = tmp_path / "audit.sqlite"
    _run_cli(
        [
            "--audit-sqlite-path",
            str(audit_path),
            "call",
            "--target",
            "mock-host",
            "--tool",
            "get_power_state",
        ],
        capsys,
    )
    connection = sqlite3.connect(audit_path)
    try:
        row = connection.execute(
            "SELECT event_index, event_json FROM audit_events ORDER BY event_index LIMIT 1"
        ).fetchone()
        record = json.loads(row[1])
        record["event"]["result"] = {"status": "tampered"}
        connection.execute(
            "UPDATE audit_events SET event_json = ? WHERE event_index = ?",
            (json.dumps(record), row[0]),
        )
        connection.commit()
    finally:
        connection.close()

    verification = verify_sqlite_audit_chain(audit_path)

    assert verification.ok is False
    assert verification.reason == "event hash mismatch"


def test_sqlite_audit_deletion_and_malformed_db_fail_closed(tmp_path, capsys) -> None:
    audit_path = tmp_path / "audit.sqlite"
    _run_cli(
        [
            "--audit-sqlite-path",
            str(audit_path),
            "call",
            "--target",
            "mock-host",
            "--tool",
            "get_power_state",
        ],
        capsys,
    )
    checkpoint = create_sqlite_audit_checkpoint(audit_path, audit_log_id="delete-test")
    connection = sqlite3.connect(audit_path)
    try:
        connection.execute(
            "DELETE FROM audit_events WHERE event_index = (SELECT max(event_index) FROM audit_events)"
        )
        connection.commit()
    finally:
        connection.close()

    verification = verify_sqlite_audit_checkpoint(audit_path, checkpoint)
    assert verification.ok is False
    assert verification.reason == "audit log tail truncated"

    malformed = tmp_path / "malformed.sqlite"
    malformed.write_text("not sqlite", encoding="utf-8")
    malformed_result = verify_sqlite_audit_chain(malformed)
    assert malformed_result.ok is False


def test_sqlite_audit_inspect_event_and_bad_identifier(tmp_path, capsys) -> None:
    audit_path = tmp_path / "audit.sqlite"
    _run_cli(
        [
            "--audit-sqlite-path",
            str(audit_path),
            "call",
            "--target",
            "mock-host",
            "--tool",
            "get_power_state",
        ],
        capsys,
    )
    events = list_sqlite_audit_events(audit_path)

    inspected = inspect_sqlite_audit_event(
        audit_path,
        event_index=events[0]["event_index"],
    )

    assert inspected["event_hash"] == events[0]["event_hash"]
    with pytest.raises(SQLiteAuditError, match="exactly one"):
        inspect_sqlite_audit_event(audit_path)


def test_cli_audit_verify_list_and_export_sqlite(tmp_path, capsys) -> None:
    audit_path = tmp_path / "audit.sqlite"
    export_path = tmp_path / "audit-export.json"
    _run_cli(
        [
            "--audit-sqlite-path",
            str(audit_path),
            "call",
            "--target",
            "mock-host",
            "--tool",
            "get_power_state",
        ],
        capsys,
    )

    verify_exit, verified = _run_cli(
        ["audit", "verify", "--sqlite-path", str(audit_path)],
        capsys,
    )
    list_exit, listed = _run_cli(
        ["audit", "list", "--sqlite-path", str(audit_path), "--limit", "5"],
        capsys,
    )
    export_exit, exported = _run_cli(
        [
            "audit",
            "export",
            "--sqlite-path",
            str(audit_path),
            "--output",
            str(export_path),
        ],
        capsys,
    )

    assert verify_exit == 0
    assert verified["status"] == "ok"
    assert list_exit == 0
    assert listed["events"]
    assert export_exit == 0
    assert exported["status"] == "ok"
    assert export_path.exists()


def test_cli_status_reports_sqlite_audit_backend(tmp_path, capsys) -> None:
    audit_path = tmp_path / "audit.sqlite"
    _run_cli(
        [
            "--audit-sqlite-path",
            str(audit_path),
            "call",
            "--target",
            "mock-host",
            "--tool",
            "get_power_state",
        ],
        capsys,
    )

    exit_code, payload = _run_cli(
        ["--audit-sqlite-path", str(audit_path), "status"],
        capsys,
    )

    assert exit_code == 0
    assert payload["audit"]["backend"] == "sqlite"
    assert payload["audit"]["hash_chain_valid"] is True
    assert payload["audit"]["verification"]["event_count"] > 0
