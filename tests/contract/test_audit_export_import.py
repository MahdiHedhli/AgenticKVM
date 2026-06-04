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


def _emit_event(path, *, reason: str) -> None:
    LocalJSONLAuditSink(path).emit(
        build_audit_event(
            event_type=AuditEventType.RESULT_RETURNED,
            correlation_id=f"export-{reason}",
            session_id="export-session",
            actor=Actor(type=ActorType.AGENT, id="agent-1"),
            capability=CapabilityRef(id="observe.status", family="observe", action="status"),
            policy_decision=PolicyDecision.ALLOW,
            result={"reason": reason},
        )
    )


def test_export_valid_audit_log_and_verify_import(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path, reason="one")
    _emit_event(audit_path, reason="two")
    checkpoint = create_audit_checkpoint(audit_path, audit_log_id="export-test")

    bundle = export_audit_log(
        audit_path,
        audit_log_id="export-test",
        checkpoint=checkpoint,
        metadata={"purpose": "contract test"},
    )
    verification = verify_audit_export(bundle)

    assert bundle["chain_verified"] is True
    assert bundle["checkpoint_verified"] is True
    assert bundle["record_count"] == 2
    assert verification.ok is True
    assert verification.reason == "audit export verified"
    assert verification.checkpoint_verified is True


def test_audit_export_detects_tampered_event(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path, reason="one")
    bundle = export_audit_log(audit_path, audit_log_id="tamper-test")

    bundle["records"][0]["event"]["result"]["reason"] = "changed"
    verification = verify_audit_export(bundle)

    assert verification.ok is False
    assert verification.reason == "audit export chain failed"


def test_audit_export_detects_deleted_middle_event(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path, reason="one")
    _emit_event(audit_path, reason="two")
    _emit_event(audit_path, reason="three")
    bundle = export_audit_log(audit_path, audit_log_id="delete-test")

    bundle["records"] = [bundle["records"][0], bundle["records"][2]]
    bundle["record_count"] = 2
    verification = verify_audit_export(bundle)

    assert verification.ok is False
    assert verification.reason == "audit export chain failed"


def test_audit_export_detects_tail_truncation_with_checkpoint(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path, reason="one")
    _emit_event(audit_path, reason="two")
    checkpoint = create_audit_checkpoint(audit_path, audit_log_id="tail-export")
    bundle = export_audit_log(
        audit_path,
        audit_log_id="tail-export",
        checkpoint=checkpoint,
    )

    bundle["records"] = bundle["records"][:1]
    bundle["record_count"] = 1
    bundle["last_event_hash"] = bundle["records"][-1]["event_hash"]
    verification = verify_audit_export(bundle)

    assert verification.ok is False
    assert verification.reason == "audit export checkpoint failed"


def test_malformed_audit_export_fails_closed() -> None:
    verification = verify_audit_export({"version": "wrong", "records": []})

    assert verification.ok is False
    assert verification.reason.startswith("audit export verification failed")


def test_audit_export_bundle_is_json_safe(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    _emit_event(audit_path, reason="one")
    bundle = export_audit_log(audit_path, audit_log_id="json-safe")

    assert json.loads(json.dumps(bundle, sort_keys=True)) == bundle
