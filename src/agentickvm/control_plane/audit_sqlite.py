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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from agentickvm.control_plane.audit import AuditEvent, AuditSink, redact_mapping
from agentickvm.control_plane.audit_checkpoint import (
    AuditCheckpoint,
    AuditCheckpointVerification,
)


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
        rows = _sqlite_rows(audit_path)
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        return SQLiteAuditVerification(ok=False, event_count=0, reason=str(exc))

    previous_hash: str | None = None
    for index, row in enumerate(rows, start=1):
        stored_previous = row["previous_hash"]
        stored_hash = row["event_hash"]
        record = row["record"]
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
    try:
        connection = sqlite3.connect(audit_path)
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
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        raise SQLiteAuditError(f"cannot list SQLite audit events: {exc}") from exc
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass


def export_sqlite_audit(
    path: str | Path,
    *,
    output_path: str | Path,
    checkpoint: AuditCheckpoint | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Export a SQLite audit log to an explicit JSON path."""

    verification = verify_sqlite_audit_chain(path)
    if not verification.ok:
        raise SQLiteAuditError(f"audit chain verification failed: {verification.reason}")
    checkpoint_payload: Mapping[str, Any] | None = None
    checkpoint_verified = False
    if checkpoint is not None:
        parsed = (
            checkpoint
            if isinstance(checkpoint, AuditCheckpoint)
            else AuditCheckpoint.from_dict(checkpoint)
        )
        checkpoint_result = verify_sqlite_audit_checkpoint(path, parsed)
        if not checkpoint_result.ok:
            raise SQLiteAuditError(
                f"audit checkpoint verification failed: {checkpoint_result.reason}"
            )
        checkpoint_payload = parsed.to_dict()
        checkpoint_verified = True
    events = list_sqlite_audit_events(path, limit=max(verification.event_count, 1))
    payload = {
        "format": "agentickvm.sqlite-audit-export.v1",
        "source": "sqlite",
        "event_count": verification.event_count,
        "verification": verification.to_dict(),
        "checkpoint": checkpoint_payload,
        "checkpoint_verified": checkpoint_verified,
        "events": list(events),
    }
    output = Path(output_path)
    if output.exists() and output.is_dir():
        raise SQLiteAuditError("audit export output path must be a file")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def inspect_sqlite_audit_event(
    path: str | Path,
    *,
    event_index: int | None = None,
    event_hash: str | None = None,
) -> dict[str, Any]:
    """Inspect one SQLite audit event by index or hash."""

    if (event_index is None) == (event_hash is None):
        raise SQLiteAuditError("provide exactly one event identifier")
    audit_path = Path(path)
    if not audit_path.exists():
        raise SQLiteAuditError("SQLite audit path does not exist")
    try:
        connection = sqlite3.connect(audit_path)
        if event_index is not None:
            row = connection.execute(
                "SELECT event_index, event_json FROM audit_events WHERE event_index = ?",
                (event_index,),
            ).fetchone()
        else:
            row = connection.execute(
                "SELECT event_index, event_json FROM audit_events WHERE event_hash = ?",
                (event_hash,),
            ).fetchone()
        if row is None:
            raise SQLiteAuditError("SQLite audit event not found")
        record = json.loads(row[1])
        return {
            "event_index": row[0],
            "event_hash": record.get("event_hash"),
            "event": record.get("event"),
        }
    except (sqlite3.Error, json.JSONDecodeError) as exc:
        raise SQLiteAuditError(f"cannot inspect SQLite audit event: {exc}") from exc
    finally:
        try:
            connection.close()
        except UnboundLocalError:
            pass


def create_sqlite_audit_checkpoint(
    path: str | Path,
    *,
    audit_log_id: str,
    metadata: Mapping[str, Any] | None = None,
    previous_checkpoint_hash: str | None = None,
    checkpoint_id: str | None = None,
    now: datetime | None = None,
) -> AuditCheckpoint:
    """Create a checkpoint from a local SQLite audit store."""

    verification = verify_sqlite_audit_chain(path)
    if not verification.ok:
        raise SQLiteAuditError(f"cannot checkpoint malformed SQLite audit: {verification.reason}")
    rows = _sqlite_rows(Path(path)) if Path(path).exists() else []
    last_hash = rows[-1]["record"].get("event_hash") if rows else None
    if last_hash is not None and not isinstance(last_hash, str):
        raise SQLiteAuditError("last SQLite audit event hash must be a string")
    return AuditCheckpoint(
        checkpoint_id=checkpoint_id or uuid4().hex,
        audit_log_id=audit_log_id,
        last_event_index=len(rows) - 1,
        event_count=len(rows),
        last_event_hash=last_hash,
        created_at=now or datetime.now(UTC),
        previous_checkpoint_hash=previous_checkpoint_hash,
        metadata=metadata or {},
    )


def verify_sqlite_audit_checkpoint(
    path: str | Path,
    checkpoint: AuditCheckpoint | Mapping[str, Any],
) -> AuditCheckpointVerification:
    """Verify a checkpoint against the current SQLite audit store."""

    try:
        parsed = (
            checkpoint
            if isinstance(checkpoint, AuditCheckpoint)
            else AuditCheckpoint.from_dict(checkpoint)
        )
        verification = verify_sqlite_audit_chain(path)
        rows = _sqlite_rows(Path(path)) if Path(path).exists() else []
        if not verification.ok:
            return _checkpoint_verification(parsed, rows, False, "audit chain failed")
        if len(rows) < parsed.event_count:
            return _checkpoint_verification(parsed, rows, False, "audit log tail truncated")
        if parsed.event_count == 0:
            return _checkpoint_verification(parsed, rows, True, "checkpoint verified")
        checkpointed_record = rows[parsed.last_event_index]["record"]
        if checkpointed_record.get("event_hash") != parsed.last_event_hash:
            return _checkpoint_verification(
                parsed,
                rows,
                False,
                "checkpoint event hash mismatch",
            )
        return _checkpoint_verification(parsed, rows, True, "checkpoint verified")
    except Exception as exc:
        if isinstance(checkpoint, AuditCheckpoint):
            audit_log_id = checkpoint.audit_log_id
            checkpoint_id = checkpoint.checkpoint_id
        elif isinstance(checkpoint, Mapping):
            audit_log_id = str(checkpoint.get("audit_log_id", "unknown"))
            checkpoint_id = str(checkpoint.get("checkpoint_id", "unknown"))
        else:
            audit_log_id = "unknown"
            checkpoint_id = "unknown"
        return AuditCheckpointVerification(
            ok=False,
            reason=f"checkpoint verification failed: {type(exc).__name__}",
            audit_log_id=audit_log_id,
            checkpoint_id=checkpoint_id,
            event_count=0,
            last_event_hash=None,
            chain_verified=False,
        )


def _last_hash(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(
        "SELECT event_hash FROM audit_events ORDER BY event_index DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return str(row[0])


def _sqlite_rows(path: Path) -> list[dict[str, Any]]:
    connection = sqlite3.connect(path)
    try:
        rows = connection.execute(
            """
            SELECT event_index, previous_hash, event_hash, event_json
            FROM audit_events
            ORDER BY event_index
            """
        )
        return [
            {
                "event_index": event_index,
                "previous_hash": previous_hash,
                "event_hash": event_hash,
                "record": json.loads(event_json),
            }
            for event_index, previous_hash, event_hash, event_json in rows
        ]
    finally:
        connection.close()


def _checkpoint_verification(
    checkpoint: AuditCheckpoint,
    rows: list[dict[str, Any]],
    ok: bool,
    reason: str,
) -> AuditCheckpointVerification:
    last_hash = rows[-1]["record"].get("event_hash") if rows else None
    return AuditCheckpointVerification(
        ok=ok,
        reason=reason,
        audit_log_id=checkpoint.audit_log_id,
        checkpoint_id=checkpoint.checkpoint_id,
        event_count=len(rows),
        last_event_hash=last_hash if isinstance(last_hash, str) else None,
        chain_verified=verify_sqlite_audit_chain_rows(rows),
    )


def verify_sqlite_audit_chain_rows(rows: list[Mapping[str, Any]]) -> bool:
    """Verify hash chaining for already-loaded SQLite audit rows."""

    previous_hash: str | None = None
    for row in rows:
        expected_previous = row.get("previous_hash")
        record = row.get("record")
        if not isinstance(record, Mapping):
            return False
        if expected_previous != previous_hash or record.get("previous_hash") != previous_hash:
            return False
        expected_hash = row.get("event_hash")
        unsigned_record = {
            "previous_hash": previous_hash,
            "event": record.get("event"),
        }
        if expected_hash != _hash_mapping(unsigned_record):
            return False
        previous_hash = expected_hash if isinstance(expected_hash, str) else None
    return True


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
    "create_sqlite_audit_checkpoint",
    "export_sqlite_audit",
    "inspect_sqlite_audit_event",
    "list_sqlite_audit_events",
    "verify_sqlite_audit_checkpoint",
    "verify_sqlite_audit_chain",
    "verify_sqlite_audit_chain_rows",
]
