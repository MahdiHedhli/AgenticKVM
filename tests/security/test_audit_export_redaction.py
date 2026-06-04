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
    export_audit_log,
    verify_audit_export,
)


def test_audit_export_redacts_secret_like_values_and_raw_bytes(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    event = build_audit_event(
        event_type=AuditEventType.RESULT_RETURNED,
        correlation_id="export-redaction",
        session_id="export-redaction-session",
        actor=Actor(type=ActorType.AGENT, id="agent-1"),
        capability=CapabilityRef(id="observe.screenshot", family="observe", action="screenshot"),
        policy_decision=PolicyDecision.ALLOW,
        request={
            "password": "must-not-leak",
            "credential_ref": "vault://prod/not-for-tests",
        },
        result={
            "artifact": {
                "kind": "screenshot",
                "raw_bytes_included": False,
            },
            "screenshot_bytes": b"synthetic-image-bytes",
            "raw_image": "synthetic-image-string",
        },
    )
    LocalJSONLAuditSink(audit_path).emit(event)
    checkpoint = create_audit_checkpoint(
        audit_path,
        audit_log_id="export-redaction",
        metadata={"api_key": "must-not-leak"},
    )

    bundle = export_audit_log(
        audit_path,
        audit_log_id="export-redaction",
        checkpoint=checkpoint,
        metadata={"bearer": "must-not-leak", "safe": "ok"},
    )
    encoded = json.dumps(bundle, sort_keys=True)
    verification = verify_audit_export(bundle)

    assert verification.ok is True
    assert "must-not-leak" not in encoded
    assert "vault://prod" not in encoded
    assert "synthetic-image-bytes" not in encoded
    assert "synthetic-image-string" not in encoded
    assert "[REDACTED]" in encoded
    assert '"raw_bytes_included": false' in encoded


def test_audit_export_uses_explicit_temp_paths_only(tmp_path) -> None:
    audit_path = tmp_path / "audit" / "events.jsonl"
    LocalJSONLAuditSink(audit_path).emit(
        build_audit_event(
            event_type=AuditEventType.RESULT_RETURNED,
            correlation_id="export-temp",
            session_id="export-temp-session",
            actor=Actor(type=ActorType.AGENT, id="agent-1"),
            capability=CapabilityRef(id="observe.status", family="observe", action="status"),
            policy_decision=PolicyDecision.ALLOW,
            result={"status": "completed"},
        )
    )

    bundle = export_audit_log(audit_path, audit_log_id="temp-export")

    assert bundle["record_count"] == 1
    assert sorted(path.name for path in tmp_path.iterdir()) == ["audit"]
