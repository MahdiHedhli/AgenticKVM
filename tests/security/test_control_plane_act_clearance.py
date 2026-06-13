from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from agentickvm.control_plane import (
    ACTClearanceVerifier,
    Actor,
    ActorType,
    ApprovalGrant,
    ApprovalGrantScope,
    ApprovalStore,
    CapabilityRequest,
    ClearanceStatus,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    InMemoryAuditSink,
    MockACTClient,
    MockACTProofVerifier,
    fingerprint_parameters,
    mode_preset,
)
from agentickvm.control_plane.act_client import cleared_response_for
from agentickvm.providers import MockProvider


NOW = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)
PARAMS = {"force": True}


def _request(params=None) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="power.force_restart",
        target_id="mock-host",
        session_id="session-1",
        correlation_id="act-clearance-test",
        requester=Actor(type=ActorType.AGENT, id="agent"),
        intended_effect="recover wedged mock fixture",
        parameters=params if params is not None else PARAMS,
        approval_request_id="clearance-1",
    )


def _control_plane(
    *,
    act_client: MockACTClient,
    provider: MockProvider | None = None,
    approval_store: ApprovalStore | None = None,
) -> ControlPlane:
    return ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=provider or MockProvider(),
        audit_sink=InMemoryAuditSink(),
        now_factory=lambda: NOW,
        approval_store=approval_store,
        clearance_client=act_client,
        clearance_verifier=ACTClearanceVerifier(
            tower_id="mock-act",
            proof_verifier=MockACTProofVerifier(),
            test_mode=True,
        ),
    )


def test_act_pending_returns_clearance_required_without_provider_execution() -> None:
    provider = MockProvider()
    control_plane = _control_plane(act_client=MockACTClient(), provider=provider)

    result = control_plane.handle(_request())

    assert result.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert result.clearance_request is not None
    assert result.clearance_request.short_code
    assert result.clearance_request.operator_message
    assert ".." not in result.clearance_request.operator_message
    assert provider.requests == []


def test_act_cleared_response_executes_matching_mock_action() -> None:
    provider = MockProvider()
    act_client = MockACTClient(default_status=ClearanceStatus.CLEARED)
    control_plane = _control_plane(act_client=act_client, provider=provider)

    result = control_plane.handle(_request())

    assert result.status == ControlPlaneStatus.COMPLETED
    assert provider.requests[-1].capability == "power.force_restart"


def test_act_denied_response_stops_execution() -> None:
    provider = MockProvider()
    act_client = MockACTClient(default_status=ClearanceStatus.DENIED)
    control_plane = _control_plane(act_client=act_client, provider=provider)

    result = control_plane.handle(_request())

    assert result.status == ControlPlaneStatus.DENIED
    assert provider.requests == []


def test_act_mismatched_clearance_stops_execution() -> None:
    request_probe = _control_plane(act_client=MockACTClient()).handle(_request())
    clearance = request_probe.clearance_request
    assert clearance is not None
    mismatched = replace(cleared_response_for(clearance), target="other-target")
    provider = MockProvider()
    act_client = MockACTClient(responses={clearance.request_id: mismatched})
    control_plane = _control_plane(act_client=act_client, provider=provider)

    result = control_plane.handle(_request())

    assert result.status == ControlPlaneStatus.DENIED
    assert result.message == "target mismatch"
    assert provider.requests == []


def test_local_approval_store_cannot_bypass_act_clearance() -> None:
    provider = MockProvider()
    store = ApprovalStore()
    store.add_action_grant(
        ApprovalGrant(
            request_id="old-local-approval",
            response_id="response-1",
            capability_id="power.force_restart",
            session_id="session-1",
            target_id="mock-host",
            provider_id="mock",
            params_fingerprint=fingerprint_parameters(PARAMS),
            expires_at=NOW + timedelta(minutes=5),
            scope=ApprovalGrantScope.ONE_TIME,
            operator=Actor(type=ActorType.OPERATOR, id="operator"),
        )
    )
    control_plane = _control_plane(
        act_client=MockACTClient(),
        provider=provider,
        approval_store=store,
    )

    result = control_plane.handle(_request())

    assert result.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert provider.requests == []
