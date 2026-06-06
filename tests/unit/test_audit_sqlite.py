from __future__ import annotations

import json
import sqlite3

from agentickvm.cli import main as cli_main
from agentickvm.control_plane import (
    export_sqlite_audit,
    list_sqlite_audit_events,
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


def test_sqlite_audit_export_is_explicit_path_json_safe(tmp_path, capsys) -> None:
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

    payload = export_sqlite_audit(audit_path, output_path=export_path)

    assert export_path.exists()
    assert payload["format"] == "agentickvm.sqlite-audit-export.v1"
    assert payload["verification"]["ok"] is True
    lowered = export_path.read_text(encoding="utf-8").lower()
    assert "password" not in lowered
    assert "api_key" not in lowered
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
