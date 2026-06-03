import json
from datetime import UTC, datetime

from agentickvm.control_plane import (
    Actor,
    ActorType,
    ApprovalGrantScope,
    ApprovalOutcome,
    ApprovalResponse,
    ApprovalStore,
    AuditEventType,
    CapabilityRequest,
    CapabilityRef,
    ControlMode,
    ControlPlane,
    InMemoryAuditSink,
    LocalJSONLAuditSink,
    PolicyDecision,
    build_audit_event,
    mode_preset,
    verify_audit_chain,
)
from agentickvm.providers import MockProvider


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _request(capability_id: str) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability_id,
        target_id="mock-host",
        session_id="s1",
        correlation_id=f"corr-{capability_id}",
        requester=Actor(type=ActorType.AGENT, id="agent-1"),
        intended_effect="audit persistence test",
        parameters={"password": "must-redact"},
    )


def test_audit_event_writes_jsonl_and_redacts_secret_values(tmp_path) -> None:
    audit_path = tmp_path / "audit" / "events.jsonl"
    sink = LocalJSONLAuditSink(audit_path)
    event = build_audit_event(
        event_type=AuditEventType.REQUEST_RECEIVED,
        correlation_id="corr-1",
        session_id="s1",
        actor=Actor(type=ActorType.AGENT, id="agent-1"),
        capability=CapabilityRef(
            id="observe.status",
            family="observe",
            action="status",
        ),
        policy_decision=PolicyDecision.ALLOW,
        target_id="mock-host",
        request={
            "password": "hidden",
            "nested": {"api_key": "hidden"},
            "detail": "safe",
        },
    )

    sink.emit(event)
    records = _records(audit_path)

    assert len(records) == 1
    assert records[0]["previous_hash"] is None
    assert records[0]["event"]["request"]["password"] == "[REDACTED]"
    assert records[0]["event"]["request"]["nested"]["api_key"] == "[REDACTED]"
    assert audit_path.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["audit"]
    assert verify_audit_chain(audit_path) is True


def test_tampered_audit_event_fails_chain_verification(tmp_path) -> None:
    audit_path = tmp_path / "events.jsonl"
    sink = LocalJSONLAuditSink(audit_path)
    event = build_audit_event(
        event_type=AuditEventType.RESULT_RETURNED,
        correlation_id="corr-1",
        session_id="s1",
        actor=Actor(type=ActorType.AGENT, id="agent-1"),
        capability=CapabilityRef(id="runtime.noop", family="runtime", action="noop"),
        policy_decision=PolicyDecision.DENY,
        result={"reason": "denied"},
    )
    sink.emit(event)

    tampered = audit_path.read_text(encoding="utf-8").replace("denied", "allowed")
    audit_path.write_text(tampered, encoding="utf-8")

    assert verify_audit_chain(audit_path) is False


def test_denied_action_is_auditable_with_local_sink(tmp_path) -> None:
    audit_path = tmp_path / "denied.jsonl"
    provider = MockProvider()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.OBSERVE),
        provider=provider,
        audit_sink=LocalJSONLAuditSink(audit_path),
    )

    engine.handle(_request("power.on"))
    event_types = [record["event"]["event_type"] for record in _records(audit_path)]

    assert "policy_decision" in event_types
    assert event_types[-1] == "result_returned"
    assert provider.requests == []
    assert verify_audit_chain(audit_path) is True


def test_approval_required_and_provider_execution_are_auditable(tmp_path) -> None:
    approval_path = tmp_path / "approval.jsonl"
    execution_path = tmp_path / "execution.jsonl"
    provider = MockProvider()

    approval_engine = ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=provider,
        audit_sink=LocalJSONLAuditSink(approval_path),
    )
    approval_engine.handle(_request("power.force_restart"))

    execution_engine = ControlPlane(
        policy=mode_preset(ControlMode.FULL_CONTROL),
        provider=provider,
        audit_sink=LocalJSONLAuditSink(execution_path),
    )
    execution_engine.handle(_request("observe.status"))

    assert "approval_requested" in [
        record["event"]["event_type"] for record in _records(approval_path)
    ]
    assert "provider_execution_completed" in [
        record["event"]["event_type"] for record in _records(execution_path)
    ]
    assert verify_audit_chain(approval_path) is True
    assert verify_audit_chain(execution_path) is True


def test_approval_consumed_is_auditable_with_local_sink(tmp_path) -> None:
    audit_path = tmp_path / "approval-consumed.jsonl"
    memory_sink = InMemoryAuditSink()
    provider = MockProvider()
    store = ApprovalStore()
    request = _request("power.force_restart")
    approval_engine = ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=provider,
        audit_sink=memory_sink,
        approval_store=store,
        now_factory=lambda: datetime(2026, 6, 3, 11, 0, tzinfo=UTC),
    )
    approval = approval_engine.handle(request).approval_request
    assert approval is not None
    store.grant_from_response(
        request=approval,
        response=ApprovalResponse(
            id="response-1",
            request_id=approval.id,
            outcome=ApprovalOutcome.GRANTED,
            operator=Actor(type=ActorType.OPERATOR, id="operator-1"),
            decided_at=datetime(2026, 6, 3, 11, 0, tzinfo=UTC),
        ),
        provider_id="mock",
        parameters={"password": "must-redact"},
        scope=ApprovalGrantScope.ONE_TIME,
    )
    resumed_engine = ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=provider,
        audit_sink=LocalJSONLAuditSink(audit_path),
        approval_store=store,
        now_factory=lambda: datetime(2026, 6, 3, 11, 1, tzinfo=UTC),
    )

    resumed_engine.handle(request)
    event_types = [record["event"]["event_type"] for record in _records(audit_path)]

    assert "approval_consumed" in event_types
    assert "provider_execution_completed" in event_types
    assert verify_audit_chain(audit_path) is True
