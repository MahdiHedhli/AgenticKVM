"""Local audit export/import verification helpers.

Exports are JSON-safe in-memory bundles for tests and future integration
contracts. This module does not upload, archive, or write bundles.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from agentickvm.control_plane.audit import redact_mapping
from agentickvm.control_plane.audit_checkpoint import (
    AuditCheckpoint,
    verify_audit_chain_records,
)

EXPORT_VERSION = "agentickvm.audit.export.v1"


class AuditExportError(ValueError):
    """Raised when an audit export bundle fails closed."""


@dataclass(frozen=True)
class AuditExportVerification:
    """Verification result for an audit export bundle."""

    ok: bool
    reason: str
    export_id: str
    audit_log_id: str
    record_count: int
    last_event_hash: str | None
    chain_verified: bool
    checkpoint_verified: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe verification payload."""

        return _json_safe(
            {
                "ok": self.ok,
                "reason": self.reason,
                "export_id": self.export_id,
                "audit_log_id": self.audit_log_id,
                "record_count": self.record_count,
                "last_event_hash": self.last_event_hash,
                "chain_verified": self.chain_verified,
                "checkpoint_verified": self.checkpoint_verified,
            }
        )


def export_audit_log(
    path: str | Path,
    *,
    audit_log_id: str,
    checkpoint: AuditCheckpoint | Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
    export_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return a redacted JSON-safe audit export bundle."""

    records = _read_records(path)
    checkpoint_payload: Mapping[str, Any] | None = None
    if checkpoint is not None:
        checkpoint_payload = (
            checkpoint.to_dict()
            if isinstance(checkpoint, AuditCheckpoint)
            else AuditCheckpoint.from_dict(checkpoint).to_dict()
        )
    chain_verified = verify_audit_chain_records(records)
    checkpoint_verified = (
        _verify_checkpoint_records(records, checkpoint_payload)
        if checkpoint_payload is not None
        else False
    )
    last_event_hash = _last_event_hash(records)
    payload = {
        "version": EXPORT_VERSION,
        "export_id": export_id or uuid4().hex,
        "created_at": (now or datetime.now(UTC)).isoformat(),
        "audit_log_id": audit_log_id,
        "records": records,
        "checkpoint": checkpoint_payload,
        "chain_verified": chain_verified,
        "checkpoint_verified": checkpoint_verified,
        "record_count": len(records),
        "last_event_hash": last_event_hash,
        "redaction_summary": _redaction_summary(records, checkpoint_payload),
        "metadata": dict(metadata or {}),
    }
    redacted, redactions = redact_mapping(payload)
    bundle = dict(redacted)
    bundle["redactions"] = sorted(set(bundle.get("redactions", []) + list(redactions)))
    return _json_safe(bundle)


def verify_audit_export(bundle: Mapping[str, Any]) -> AuditExportVerification:
    """Verify an audit export bundle without writing files."""

    try:
        if bundle.get("version") != EXPORT_VERSION:
            raise AuditExportError("unsupported audit export version")
        export_id = _required_str(bundle, "export_id")
        audit_log_id = _required_str(bundle, "audit_log_id")
        records = _records_from_bundle(bundle)
        expected_count = _required_int(bundle, "record_count")
        if len(records) != expected_count:
            return AuditExportVerification(
                ok=False,
                reason="audit export record count mismatch",
                export_id=export_id,
                audit_log_id=audit_log_id,
                record_count=len(records),
                last_event_hash=_last_event_hash(records),
                chain_verified=False,
                checkpoint_verified=False,
            )
        chain_verified = verify_audit_chain_records(records)
        if not chain_verified:
            return AuditExportVerification(
                ok=False,
                reason="audit export chain failed",
                export_id=export_id,
                audit_log_id=audit_log_id,
                record_count=len(records),
                last_event_hash=_last_event_hash(records),
                chain_verified=False,
                checkpoint_verified=False,
            )
        expected_last_hash = bundle.get("last_event_hash")
        if expected_last_hash != _last_event_hash(records):
            return AuditExportVerification(
                ok=False,
                reason="audit export last hash mismatch",
                export_id=export_id,
                audit_log_id=audit_log_id,
                record_count=len(records),
                last_event_hash=_last_event_hash(records),
                chain_verified=True,
                checkpoint_verified=False,
            )
        checkpoint_payload = bundle.get("checkpoint")
        checkpoint_verified = False
        if checkpoint_payload is not None:
            if not isinstance(checkpoint_payload, Mapping):
                raise AuditExportError("checkpoint must be an object")
            checkpoint_verified = _verify_checkpoint_records(records, checkpoint_payload)
            if not checkpoint_verified:
                return AuditExportVerification(
                    ok=False,
                    reason="audit export checkpoint failed",
                    export_id=export_id,
                    audit_log_id=audit_log_id,
                    record_count=len(records),
                    last_event_hash=_last_event_hash(records),
                    chain_verified=True,
                    checkpoint_verified=False,
                )
        return AuditExportVerification(
            ok=True,
            reason="audit export verified",
            export_id=export_id,
            audit_log_id=audit_log_id,
            record_count=len(records),
            last_event_hash=_last_event_hash(records),
            chain_verified=True,
            checkpoint_verified=checkpoint_verified,
        )
    except Exception as exc:
        return AuditExportVerification(
            ok=False,
            reason=f"audit export verification failed: {type(exc).__name__}",
            export_id=str(bundle.get("export_id", "unknown"))
            if isinstance(bundle, Mapping)
            else "unknown",
            audit_log_id=str(bundle.get("audit_log_id", "unknown"))
            if isinstance(bundle, Mapping)
            else "unknown",
            record_count=0,
            last_event_hash=None,
            chain_verified=False,
            checkpoint_verified=False,
        )


def _verify_checkpoint_records(
    records: list[Mapping[str, Any]],
    checkpoint_payload: Mapping[str, Any],
) -> bool:
    checkpoint = AuditCheckpoint.from_dict(checkpoint_payload)
    if len(records) < checkpoint.event_count:
        return False
    if checkpoint.event_count == 0:
        return True
    return (
        records[checkpoint.last_event_index].get("event_hash")
        == checkpoint.last_event_hash
    )


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
                raise AuditExportError("audit record must be an object")
            records.append(record)
    return records


def _records_from_bundle(bundle: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    records = bundle.get("records")
    if not isinstance(records, list):
        raise AuditExportError("records must be a list")
    parsed: list[Mapping[str, Any]] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise AuditExportError("export record must be an object")
        parsed.append(record)
    return parsed


def _last_event_hash(records: list[Mapping[str, Any]]) -> str | None:
    if not records:
        return None
    value = records[-1].get("event_hash")
    return value if isinstance(value, str) else None


def _redaction_summary(
    records: list[Mapping[str, Any]],
    checkpoint: Mapping[str, Any] | None,
) -> dict[str, Any]:
    record_redactions = 0
    for record in records:
        event = record.get("event")
        if isinstance(event, Mapping):
            redactions = event.get("redactions")
            if isinstance(redactions, list):
                record_redactions += len(redactions)
    checkpoint_redactions = 0
    if checkpoint is not None:
        redactions = checkpoint.get("redactions")
        if isinstance(redactions, list):
            checkpoint_redactions = len(redactions)
    return {
        "record_redaction_count": record_redactions,
        "checkpoint_redaction_count": checkpoint_redactions,
    }


def _required_str(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise AuditExportError(f"{key} is required")
    return value


def _required_int(values: Mapping[str, Any], key: str) -> int:
    value = values.get(key)
    if not isinstance(value, int):
        raise AuditExportError(f"{key} must be an integer")
    return value


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


__all__ = [
    "AuditExportError",
    "AuditExportVerification",
    "EXPORT_VERSION",
    "export_audit_log",
    "verify_audit_export",
]
