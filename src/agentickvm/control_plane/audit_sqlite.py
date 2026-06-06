"""Local SQLite audit backend.

This backend is a production-readiness v1 scaffold built on the Python
standard library. It is explicit-path only and stores the same redacted,
hash-chained audit records as the local JSONL sink.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from agentickvm.control_plane.audit import AuditEvent, AuditSink, redact_mapping


class SQLiteAuditError(ValueError):
    """Raised when SQLite audit verification or export fails closed."""


@dataclass(frozen=True)
class SQLiteAuditVerification:
    """SQLite audit verification result."""

    ok: bool
    event_count: int
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe verification payload."""

        return {
            "ok": self.ok,
            "event_count": self.event_count,
            "reason": self.reason,
        }


class SQLiteAuditSink(AuditSink):
    """SQLite-backed audit sink with a tamper-evident hash chain."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.exists() and self.path.is_dir():
            raise ValueError("SQLite audit path must be a file")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._initialize()

    def emit(self, event: AuditEvent) -> None:
        """Persist one redacted audit event."""

        previous_hash = _last_hash(self._connection)
        event_payload = _redacted_payload(event)
        unsigned_record = {
            "previous_hash": previous_hash,
            "event": event_payload,
        }
        event_hash = _hash_mapping(unsigned_record)
        record = {
            **unsigned_record,
            "event_hash": event_hash,
        }
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO audit_events
                    (previous_hash, event_hash, event_json)
                VALUES (?, ?, ?)
                """,
                (
                    previous_hash,
                    event_hash,
                    json.dumps(record, sort_keys=True, separators=(",", ":")),
                ),
            )

    def close(self) -> None:
        """Close the SQLite connection."""

        self._connection.close()

    def _initialize(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_index INTEGER PRIMARY KEY AUTOINCREMENT,
                    previous_hash TEXT,
                    event_hash TEXT NOT NULL,
                    event_json TEXT NOT NULL
                )
                """
            )


def verify_sqlite_audit_chain(path: str | Path) -> SQLiteAuditVerification:
    """Verify a local SQLite audit hash chain."""

    audit_path = Path(path)
    if not audit_path.exists():
        return SQLiteAuditVerification(ok=True, event_count=0)
    try:
        connection = sqlite3.connect(audit_path)
        rows = list(
            connection.execute(
                "SELECT previous_hash, event_hash, event_json FROM audit_events ORDER BY event_index"
            )
        )
    except sqlite3.Error as exc:
        return SQLiteAuditVerification(ok=False, event_count=0, reason=str(exc))
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass

    previous_hash: str | None = None
    for index, (stored_previous, stored_hash, event_json) in enumerate(rows, start=1):
        try:
            record = json.loads(event_json)
        except json.JSONDecodeError:
            return SQLiteAuditVerification(
                ok=False,
                event_count=index - 1,
                reason="malformed audit record",
            )
        if stored_previous != previous_hash or record.get("previous_hash") != previous_hash:
            return SQLiteAuditVerification(
                ok=False,
                event_count=index - 1,
                reason="previous hash mismatch",
            )
        unsigned_record = {
            "previous_hash": previous_hash,
            "event": record.get("event"),
        }
        expected_hash = _hash_mapping(unsigned_record)
        if stored_hash != expected_hash or record.get("event_hash") != expected_hash:
            return SQLiteAuditVerification(
                ok=False,
                event_count=index - 1,
                reason="event hash mismatch",
            )
        previous_hash = expected_hash
    return SQLiteAuditVerification(ok=True, event_count=len(rows))


def list_sqlite_audit_events(path: str | Path, *, limit: int = 20) -> tuple[dict[str, Any], ...]:
    """Return recent SQLite audit events as JSON-safe dictionaries."""

    if limit <= 0:
        raise SQLiteAuditError("audit event limit must be positive")
    audit_path = Path(path)
    if not audit_path.exists():
        return ()
    connection = sqlite3.connect(audit_path)
    try:
        rows = connection.execute(
            """
            SELECT event_index, event_json
            FROM audit_events
            ORDER BY event_index DESC
            LIMIT ?
            """,
            (limit,),
        )
        events = []
        for event_index, event_json in rows:
            record = json.loads(event_json)
            events.append(
                {
                    "event_index": event_index,
                    "event_hash": record.get("event_hash"),
                    "event": record.get("event"),
                }
            )
        return tuple(reversed(events))
    finally:
        connection.close()


def export_sqlite_audit(
    path: str | Path,
    *,
    output_path: str | Path,
) -> dict[str, Any]:
    """Export a SQLite audit log to an explicit JSON path."""

    verification = verify_sqlite_audit_chain(path)
    if not verification.ok:
        raise SQLiteAuditError(f"audit chain verification failed: {verification.reason}")
    events = list_sqlite_audit_events(path, limit=max(verification.event_count, 1))
    payload = {
        "format": "agentickvm.sqlite-audit-export.v1",
        "source": "sqlite",
        "event_count": verification.event_count,
        "verification": verification.to_dict(),
        "events": list(events),
    }
    output = Path(output_path)
    if output.exists() and output.is_dir():
        raise SQLiteAuditError("audit export output path must be a file")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _last_hash(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(
        "SELECT event_hash FROM audit_events ORDER BY event_index DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return str(row[0])


def _redacted_payload(event: AuditEvent) -> dict[str, Any]:
    payload = event.to_dict()
    redactions = set(payload.get("redactions", []))
    for section in ("request", "result", "approval"):
        section_value = payload.get(section)
        if isinstance(section_value, Mapping):
            redacted, paths = redact_mapping(section_value)
            payload[section] = dict(redacted)
            redactions.update(f"{section}.{path}" for path in paths)
    payload["redactions"] = sorted(redactions)
    return payload


def _hash_mapping(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "SQLiteAuditError",
    "SQLiteAuditSink",
    "SQLiteAuditVerification",
    "export_sqlite_audit",
    "list_sqlite_audit_events",
    "verify_sqlite_audit_chain",
]
