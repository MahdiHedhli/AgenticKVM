import json
from datetime import UTC, datetime

import pytest

from agentickvm.control_plane import (
    Actor,
    ActorType,
    AuditCheckpoint,
    AuditCheckpointError,
    AuditEventType,
    CapabilityRef,
    LocalJSONLAuditSink,
    PolicyDecision,
    build_audit_event,
    create_audit_checkpoint,
    verify_audit_checkpoint,
)


def _emit_event(path, *, reason: str) -> None:
    LocalJSONLAuditSink(path).emit(
        build_audit_event(
            event_type=AuditEventType.RESULT_RETURNED,
            correlation_id=f"corr-{reason}",
            session_id="checkpoint-session",
            actor=Actor(type=ActorType.AGENT, id="agent-1"),
            capability=CapabilityRef(id="observe.status", family="observe", action="status"),
            policy_decision=PolicyDecision.ALLOW,
            result={"reason": reason},
        )
    )


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_checkpoint_created_from_valid_audit_log_and_round_trips(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path, reason="one")
    _emit_event(audit_path, reason="two")

    checkpoint = create_audit_checkpoint(
        audit_path,
        audit_log_id="local-test",
        metadata={"operator": "tester"},
        checkpoint_id="checkpoint-1",
        now=datetime(2026, 6, 4, 3, 0, tzinfo=UTC),
    )
    parsed = AuditCheckpoint.from_dict(checkpoint.to_dict())
    verification = verify_audit_checkpoint(audit_path, parsed)

    assert checkpoint.event_count == 2
    assert checkpoint.last_event_index == 1
    assert checkpoint.last_event_hash == _records(audit_path)[-1]["event_hash"]
    assert parsed.to_dict() == checkpoint.to_dict()
    assert verification.ok is True
    assert verification.reason == "checkpoint verified"


def test_checkpoint_detects_tail_truncation_after_checkpoint(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path, reason="one")
    _emit_event(audit_path, reason="two")
    checkpoint = create_audit_checkpoint(audit_path, audit_log_id="tail-test")

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    audit_path.write_text(lines[0] + "\n", encoding="utf-8")

    verification = verify_audit_checkpoint(audit_path, checkpoint)

    assert verification.ok is False
    assert verification.reason == "audit log tail truncated"


def test_checkpoint_detects_last_hash_mismatch_and_event_count_mismatch(
    tmp_path,
) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path, reason="one")
    _emit_event(audit_path, reason="two")
    checkpoint = create_audit_checkpoint(audit_path, audit_log_id="hash-test")
    records = _records(audit_path)
    records[checkpoint.last_event_index]["event_hash"] = "0" * 64
    audit_path.write_text(
        "\n".join(json.dumps(record, sort_keys=True) for record in records) + "\n",
        encoding="utf-8",
    )

    verification = verify_audit_checkpoint(audit_path, checkpoint)

    assert verification.ok is False
    assert verification.reason in {
        "audit chain failed",
        "checkpoint event hash mismatch",
    }


def test_checkpoint_allows_append_after_checkpoint(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path, reason="one")
    checkpoint = create_audit_checkpoint(audit_path, audit_log_id="append-test")

    _emit_event(audit_path, reason="two")

    verification = verify_audit_checkpoint(audit_path, checkpoint)

    assert verification.ok is True
    assert verification.event_count == 2


def test_malformed_checkpoint_and_malformed_audit_log_fail_closed(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path, reason="one")
    checkpoint = create_audit_checkpoint(audit_path, audit_log_id="malformed-test")
    bad_payload = checkpoint.to_dict()
    bad_payload["event_count"] = "not-an-int"

    with pytest.raises(AuditCheckpointError, match="event_count"):
        AuditCheckpoint.from_dict(bad_payload)

    audit_path.write_text("{not-json}\n", encoding="utf-8")
    verification = verify_audit_checkpoint(audit_path, checkpoint)

    assert verification.ok is False
    assert verification.chain_verified is False
