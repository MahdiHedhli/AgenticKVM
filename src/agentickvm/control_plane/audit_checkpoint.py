"""Audit checkpoint model for tail-truncation detection.

Checkpoints are local, JSON-safe metadata records. They do not modify audit
logs and do not provide a production signing backend.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from uuid import uuid4

from agentickvm.control_plane.audit import redact_mapping, verify_audit_chain


class AuditCheckpointError(ValueError):
    """Raised when checkpoint creation or parsing fails closed."""


@dataclass(frozen=True)
class AuditCheckpoint:
    """Checkpoint for a local audit JSONL hash chain."""

    checkpoint_id: str
    audit_log_id: str
    last_event_index: int
    event_count: int
    last_event_hash: str | None
    created_at: datetime
    previous_checkpoint_hash: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    checkpoint_hash: str | None = None
    redactions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.checkpoint_id:
            raise AuditCheckpointError("checkpoint_id is required")
        if not self.audit_log_id:
            raise AuditCheckpointError("audit_log_id is required")
        if self.event_count < 0:
            raise AuditCheckpointError("event_count cannot be negative")
        if self.last_event_index != self.event_count - 1:
            raise AuditCheckpointError("last_event_index must match event_count")
        if self.event_count == 0 and self.last_event_hash is not None:
            raise AuditCheckpointError("empty checkpoint cannot have last_event_hash")
        if self.event_count > 0 and not self.last_event_hash:
            raise AuditCheckpointError("non-empty checkpoint requires last_event_hash")

        safe_metadata, redactions = redact_mapping(dict(self.metadata))
        object.__setattr__(self, "metadata", MappingProxyType(dict(safe_metadata)))
        object.__setattr__(
            self,
            "redactions",
            tuple(self.redactions) + tuple(f"metadata.{path}" for path in redactions),
        )
        expected_hash = _checkpoint_hash(self._unsigned_payload())
        if self.checkpoint_hash is None:
            object.__setattr__(self, "checkpoint_hash", expected_hash)
        elif self.checkpoint_hash != expected_hash:
            raise AuditCheckpointError("checkpoint_hash does not match content")

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "AuditCheckpoint":
        """Parse and verify a checkpoint payload."""

        return cls(
            checkpoint_id=_required_str(payload, "checkpoint_id"),
            audit_log_id=_required_str(payload, "audit_log_id"),
            last_event_index=_required_int(payload, "last_event_index"),
            event_count=_required_int(payload, "event_count"),
            last_event_hash=_optional_str(payload.get("last_event_hash")),
            created_at=_datetime_from_value(payload.get("created_at")),
            previous_checkpoint_hash=_optional_str(
                payload.get("previous_checkpoint_hash")
            ),
            metadata=_mapping(payload.get("metadata", {}), "metadata"),
            checkpoint_hash=_required_str(payload, "checkpoint_hash"),
            redactions=tuple(str(item) for item in payload.get("redactions", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe checkpoint payload."""

        payload = self._unsigned_payload()
        payload["checkpoint_hash"] = self.checkpoint_hash
        return _json_safe(payload)

    def _unsigned_payload(self) -> dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "audit_log_id": self.audit_log_id,
            "last_event_index": self.last_event_index,
            "event_count": self.event_count,
            "last_event_hash": self.last_event_hash,
            "created_at": self.created_at.isoformat(),
            "previous_checkpoint_hash": self.previous_checkpoint_hash,
            "metadata": dict(self.metadata),
            "redactions": sorted(set(self.redactions)),
        }


@dataclass(frozen=True)
class AuditCheckpointVerification:
    """Verification result for a checkpoint against an audit log."""

    ok: bool
    reason: str
    audit_log_id: str
    checkpoint_id: str
    event_count: int
    last_event_hash: str | None
    chain_verified: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe verification payload."""

        return _json_safe(
            {
                "ok": self.ok,
                "reason": self.reason,
                "audit_log_id": self.audit_log_id,
                "checkpoint_id": self.checkpoint_id,
                "event_count": self.event_count,
                "last_event_hash": self.last_event_hash,
                "chain_verified": self.chain_verified,
            }
        )


def create_audit_checkpoint(
    path: str | Path,
    *,
    audit_log_id: str,
    metadata: Mapping[str, Any] | None = None,
    previous_checkpoint_hash: str | None = None,
    checkpoint_id: str | None = None,
    now: datetime | None = None,
) -> AuditCheckpoint:
    """Create a checkpoint from a local audit JSONL file."""

    records = _read_records(path)
    if not verify_audit_chain(path):
        raise AuditCheckpointError("cannot checkpoint malformed audit chain")
    event_count = len(records)
    last_event_hash = records[-1].get("event_hash") if records else None
    if last_event_hash is not None and not isinstance(last_event_hash, str):
        raise AuditCheckpointError("last event hash must be a string")
    return AuditCheckpoint(
        checkpoint_id=checkpoint_id or uuid4().hex,
        audit_log_id=audit_log_id,
        last_event_index=event_count - 1,
        event_count=event_count,
        last_event_hash=last_event_hash,
        created_at=now or datetime.now(UTC),
        previous_checkpoint_hash=previous_checkpoint_hash,
        metadata=metadata or {},
    )


def verify_audit_checkpoint(
    path: str | Path,
    checkpoint: AuditCheckpoint | Mapping[str, Any],
) -> AuditCheckpointVerification:
    """Verify a checkpoint against the current audit JSONL file."""

    try:
        parsed = (
            checkpoint
            if isinstance(checkpoint, AuditCheckpoint)
            else AuditCheckpoint.from_dict(checkpoint)
        )
        records = _read_records(path)
        chain_verified = verify_audit_chain(path)
        if not chain_verified:
            return _verification(parsed, records, False, "audit chain failed")
        if len(records) < parsed.event_count:
            return _verification(parsed, records, False, "audit log tail truncated")
        if parsed.event_count == 0:
            return _verification(parsed, records, True, "checkpoint verified")
        checkpointed_record = records[parsed.last_event_index]
        if checkpointed_record.get("event_hash") != parsed.last_event_hash:
            return _verification(parsed, records, False, "checkpoint event hash mismatch")
        return _verification(parsed, records, True, "checkpoint verified")
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


def _verification(
    checkpoint: AuditCheckpoint,
    records: list[Mapping[str, Any]],
    ok: bool,
    reason: str,
) -> AuditCheckpointVerification:
    last_hash = records[-1].get("event_hash") if records else None
    return AuditCheckpointVerification(
        ok=ok,
        reason=reason,
        audit_log_id=checkpoint.audit_log_id,
        checkpoint_id=checkpoint.checkpoint_id,
        event_count=len(records),
        last_event_hash=last_hash if isinstance(last_hash, str) else None,
        chain_verified=verify_audit_chain_records(records),
    )


def verify_audit_chain_records(records: list[Mapping[str, Any]]) -> bool:
    """Verify hash chaining for already-loaded records."""

    previous_hash: str | None = None
    for record in records:
        expected_previous = record.get("previous_hash")
        if expected_previous != previous_hash:
            return False
        expected_hash = record.get("event_hash")
        unsigned_record = {
            "previous_hash": expected_previous,
            "event": record.get("event"),
        }
        if expected_hash != _hash_mapping(unsigned_record):
            return False
        previous_hash = expected_hash if isinstance(expected_hash, str) else None
    return True


def _read_records(path: str | Path) -> list[Mapping[str, Any]]:
    audit_path = Path(path)
    if not audit_path.exists():
        return []
    records: list[Mapping[str, Any]] = []
    with audit_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, Mapping):
                raise AuditCheckpointError("audit record must be an object")
            records.append(record)
    return records


def _checkpoint_hash(payload: Mapping[str, Any]) -> str:
    return _hash_mapping(payload)


def _hash_mapping(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _required_str(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise AuditCheckpointError(f"{key} is required")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AuditCheckpointError("optional checkpoint string fields must be strings")
    return value


def _required_int(values: Mapping[str, Any], key: str) -> int:
    value = values.get(key)
    if not isinstance(value, int):
        raise AuditCheckpointError(f"{key} must be an integer")
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AuditCheckpointError(f"{name} must be an object")
    return value


def _datetime_from_value(value: Any) -> datetime:
    if not isinstance(value, str) or not value:
        raise AuditCheckpointError("created_at must be an ISO datetime string")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


__all__ = [
    "AuditCheckpoint",
    "AuditCheckpointError",
    "AuditCheckpointVerification",
    "create_audit_checkpoint",
    "verify_audit_checkpoint",
    "verify_audit_chain_records",
]
