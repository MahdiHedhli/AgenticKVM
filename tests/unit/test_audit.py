from agentickvm.control_plane import (
    DEFAULT_CAPABILITY_REGISTRY,
    Actor,
    ActorType,
    AuditEventType,
    CapabilityRef,
    InMemoryAuditSink,
    PolicyDecision,
    build_audit_event,
)


def test_build_audit_event_redacts_request_and_result() -> None:
    capability = CapabilityRef.from_capability(
        DEFAULT_CAPABILITY_REGISTRY.require("input.keyboard_type")
    )

    event = build_audit_event(
        event_type=AuditEventType.POLICY_DECISION,
        correlation_id="corr-1",
        session_id="s1",
        target_id="lab-a",
        actor=Actor(type=ActorType.AGENT, id="agent-1"),
        capability=capability,
        policy_decision=PolicyDecision.ASK_EACH_TIME,
        request={"text": "typed secret", "nested": {"api_token": "abc"}},
        result={"ok": True, "password": "hidden"},
        material_risks=("dangerous action",),
    )
    payload = event.to_dict()

    assert payload["event_type"] == "policy_decision"
    assert payload["request"]["text"] == "[REDACTED]"
    assert payload["request"]["nested"]["api_token"] == "[REDACTED]"
    assert payload["result"]["password"] == "[REDACTED]"
    assert set(payload["redactions"]) == {
        "request.text",
        "request.nested.api_token",
        "result.password",
    }
    assert payload["material_risks"] == ["dangerous action"]


def test_in_memory_audit_sink_records_events() -> None:
    capability = CapabilityRef.from_capability(
        DEFAULT_CAPABILITY_REGISTRY.require("observe.status")
    )
    event = build_audit_event(
        event_type=AuditEventType.REQUEST_RECEIVED,
        correlation_id="corr-1",
        session_id="s1",
        target_id="lab-a",
        actor=Actor(type=ActorType.TEST, id="test"),
        capability=capability,
        policy_decision=PolicyDecision.ALLOW,
    )
    sink = InMemoryAuditSink()

    sink.emit(event)

    assert sink.events == [event]
