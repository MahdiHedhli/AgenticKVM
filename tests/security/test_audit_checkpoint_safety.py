import json

from agentickvm.control_plane import (
    Actor,
    ActorType,
    AuditEventType,
    CapabilityRef,
    LocalJSONLAuditSink,
    PolicyDecision,
    build_audit_event,
    create_audit_checkpoint,
    verify_audit_checkpoint,
)


def _emit_event(path) -> None:
    LocalJSONLAuditSink(path).emit(
        build_audit_event(
            event_type=AuditEventType.RESULT_RETURNED,
            correlation_id="checkpoint-safety",
            session_id="checkpoint-safety-session",
            actor=Actor(type=ActorType.AGENT, id="agent-1"),
            capability=CapabilityRef(id="observe.status", family="observe", action="status"),
            policy_decision=PolicyDecision.ALLOW,
            result={"status": "completed"},
        )
    )


def test_checkpoint_metadata_redacts_secret_like_values(tmp_path) -> None:
    audit_path = tmp_path / "audit" / "events.jsonl"
    _emit_event(audit_path)

    checkpoint = create_audit_checkpoint(
        audit_path,
        audit_log_id="safety-test",
        metadata={
            "safe": "metadata",
            "credential_ref": "vault://prod/not-for-tests",
            "nested": {"api_key": "must-not-leak"},
            "artifact": {"raw_image": "synthetic-bytes"},
        },
    )
    encoded = json.dumps(checkpoint.to_dict(), sort_keys=True)

    assert "vault://prod" not in encoded
    assert "must-not-leak" not in encoded
    assert "synthetic-bytes" not in encoded
    assert encoded.count("[REDACTED]") >= 3
    assert sorted(path.name for path in tmp_path.iterdir()) == ["audit"]


def test_checkpoint_does_not_modify_audit_log(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path)
    before = audit_path.read_text(encoding="utf-8")

    checkpoint = create_audit_checkpoint(audit_path, audit_log_id="no-modify")
    verification = verify_audit_checkpoint(audit_path, checkpoint)

    assert audit_path.read_text(encoding="utf-8") == before
    assert verification.ok is True


def test_checkpoint_verification_uses_json_safe_output(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path)
    checkpoint = create_audit_checkpoint(audit_path, audit_log_id="json-safe")
    verification = verify_audit_checkpoint(audit_path, checkpoint)

    payload = verification.to_dict()

    assert json.loads(json.dumps(payload, sort_keys=True)) == payload
    assert "password" not in json.dumps(payload).lower()
    assert "token" not in json.dumps(payload).lower()
