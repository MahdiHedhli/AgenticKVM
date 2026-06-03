from datetime import UTC, datetime, timedelta

import pytest

from agentickvm.control_plane import (
    DEFAULT_CAPABILITY_REGISTRY,
    Actor,
    ActorType,
    ApprovalOutcome,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalStore,
    EmergencyStopActive,
    EmergencyStopState,
    PolicyDecision,
    SessionApprovalGrant,
    build_approval_request,
    mode_preset,
)
from agentickvm.control_plane.approvals import CapabilityRef
from agentickvm.control_plane.decisions import ControlMode


def test_build_approval_request_is_explainable_and_schema_shaped() -> None:
    capability = DEFAULT_CAPABILITY_REGISTRY.require("storage.wipe_disk")
    policy = mode_preset(ControlMode.SUPERVISED)
    decision = policy.decision_for(
        capability.id,
        target_id="lab-a",
        session_id="s1",
    )
    now = datetime(2026, 6, 3, 3, 45, tzinfo=UTC)
    ids = iter(["approval-1", "audit-1"])

    request = build_approval_request(
        decision_result=decision,
        capability=capability,
        session_id="s1",
        requester=Actor(type=ActorType.AGENT, id="agent-1"),
        target_ids=("lab-a",),
        intended_effect="erase test disk fixture",
        now=now,
        id_factory=lambda: next(ids),
    )
    payload = request.to_dict()

    assert request.id == "approval-1"
    assert request.expires_at == now + timedelta(minutes=15)
    assert payload["capability"]["id"] == "storage.wipe_disk"
    assert payload["policy_decision"] == "ask_each_time"
    assert payload["target_scope"]["targets"] == ["lab-a"]
    assert "erase test disk fixture" in payload["operator_message"]
    assert "destructive action" in payload["material_risks"]
    assert payload["proposed_audit_event_id"] == "audit-1"


def test_approval_request_rejects_non_ask_decision() -> None:
    capability = CapabilityRef(id="observe.status", family="observe", action="status")

    with pytest.raises(ValueError, match="ask policy decision"):
        ApprovalRequest(
            id="approval-1",
            created_at=datetime(2026, 6, 3, 3, 45, tzinfo=UTC),
            expires_at=datetime(2026, 6, 3, 4, 0, tzinfo=UTC),
            session_id="s1",
            requester=Actor(type=ActorType.AGENT, id="agent-1"),
            capability=capability,
            target_ids=("lab-a",),
            policy_decision=PolicyDecision.ALLOW,
            operator_message="not needed",
            material_risks=("none",),
            proposed_audit_event_id="audit-1",
        )


def test_approval_response_requires_operator_actor() -> None:
    with pytest.raises(ValueError, match="operator actor"):
        ApprovalResponse(
            id="response-1",
            request_id="approval-1",
            outcome=ApprovalOutcome.GRANTED,
            operator=Actor(type=ActorType.AGENT, id="agent-1"),
            decided_at=datetime(2026, 6, 3, 3, 46, tzinfo=UTC),
        )


def test_session_approval_grant_matches_exact_scope_and_ttl() -> None:
    now = datetime(2026, 6, 3, 3, 45, tzinfo=UTC)
    grant = SessionApprovalGrant(
        request_id="approval-1",
        capability_id="media.mount_approved_iso",
        session_id="s1",
        target_ids=frozenset({"lab-a"}),
        expires_at=now + timedelta(minutes=5),
    )
    store = ApprovalStore()
    store.add(grant)

    assert store.find(
        capability_id="media.mount_approved_iso",
        session_id="s1",
        target_id="lab-a",
        now=now,
    ) is grant
    assert store.find(
        capability_id="media.mount_approved_iso",
        session_id="s2",
        target_id="lab-a",
        now=now,
    ) is None
    assert store.find(
        capability_id="media.mount_approved_iso",
        session_id="s1",
        target_id="lab-a",
        now=now + timedelta(minutes=6),
    ) is None


def test_emergency_stop_state_blocks_when_active() -> None:
    inactive = EmergencyStopState()
    active = EmergencyStopState(
        active=True,
        reason="operator stop",
        activated_by=Actor(type=ActorType.OPERATOR, id="operator-1"),
    )

    inactive.require_clear()
    with pytest.raises(EmergencyStopActive, match="operator stop"):
        active.require_clear()
