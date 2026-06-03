from datetime import UTC, datetime, timedelta

import pytest

from agentickvm.control_plane import (
    Actor,
    ActorType,
    ApprovalGrant,
    ApprovalGrantScope,
    ApprovalOutcome,
    ApprovalResponse,
    ApprovalStore,
    CapabilityRequest,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    InMemoryAuditSink,
    mode_preset,
)
from agentickvm.providers import MockProvider

NOW = datetime(2026, 6, 3, 11, 0, tzinfo=UTC)


class OtherMockProvider(MockProvider):
    provider_id = "other-mock"


def _request(
    capability_id: str = "power.force_restart",
    *,
    target_id: str = "lab-a",
    params: dict | None = None,
) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability_id,
        target_id=target_id,
        session_id="s1",
        correlation_id=f"corr-{capability_id}-{target_id}",
        requester=Actor(type=ActorType.AGENT, id="agent-1"),
        intended_effect="test approval resumption",
        parameters=params or {},
    )


def _engine(
    *,
    provider=None,
    store: ApprovalStore | None = None,
    sink: InMemoryAuditSink | None = None,
    now: datetime = NOW,
) -> tuple[ControlPlane, MockProvider, InMemoryAuditSink, ApprovalStore]:
    resolved_provider = provider or MockProvider()
    resolved_sink = sink or InMemoryAuditSink()
    resolved_store = store or ApprovalStore()
    return (
        ControlPlane(
            policy=mode_preset(ControlMode.SUPERVISED),
            provider=resolved_provider,
            audit_sink=resolved_sink,
            approval_store=resolved_store,
            now_factory=lambda: now,
        ),
        resolved_provider,
        resolved_sink,
        resolved_store,
    )


def _approve(
    store: ApprovalStore,
    approval_request,
    *,
    params: dict | None = None,
    provider_id: str = "mock",
    scope: ApprovalGrantScope = ApprovalGrantScope.ONE_TIME,
) -> None:
    response = ApprovalResponse(
        id=f"response-{approval_request.id}",
        request_id=approval_request.id,
        outcome=ApprovalOutcome.GRANTED,
        operator=Actor(type=ActorType.OPERATOR, id="operator-1"),
        decided_at=NOW,
    )
    store.grant_from_response(
        request=approval_request,
        response=response,
        provider_id=provider_id,
        parameters=params or {},
        scope=scope,
    )


def test_approval_required_result_can_produce_approval_request() -> None:
    engine, provider, _sink, _store = _engine()

    result = engine.handle(_request())

    assert result.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert result.approval_request is not None
    assert result.approval_request.provider_id == "mock"
    assert result.approval_request.capability.id == "power.force_restart"
    assert provider.requests == []


def test_one_time_approval_resumes_exactly_one_matching_mock_action() -> None:
    engine, provider, sink, store = _engine()
    request = _request(params={"reason": "test"})
    approval = engine.handle(request).approval_request
    assert approval is not None
    _approve(store, approval, params={"reason": "test"})

    resumed = engine.handle(request)
    second = engine.handle(request)

    assert resumed.status == ControlPlaneStatus.COMPLETED
    assert resumed.provider_result is not None
    assert resumed.provider_result.performed_on_hardware is False
    assert second.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert len(provider.requests) == 1
    assert "approval_consumed" in [event.event_type.value for event in sink.events]


def test_session_approval_allows_matching_capability_within_session() -> None:
    engine, provider, _sink, store = _engine()
    request = _request(params={"reason": "session"})
    approval = engine.handle(request).approval_request
    assert approval is not None
    _approve(
        store,
        approval,
        params={"reason": "session"},
        scope=ApprovalGrantScope.SESSION,
    )

    first = engine.handle(request)
    second = engine.handle(request)

    assert first.status == ControlPlaneStatus.COMPLETED
    assert second.status == ControlPlaneStatus.COMPLETED
    assert len(provider.requests) == 2


def test_approval_cannot_be_reused_for_different_capability() -> None:
    engine, provider, _sink, store = _engine()
    approval = engine.handle(_request("power.force_restart")).approval_request
    assert approval is not None
    _approve(store, approval)

    result = engine.handle(_request("power.graceful_restart"))

    assert result.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert provider.requests == []


def test_approval_cannot_be_reused_for_different_target() -> None:
    engine, provider, _sink, store = _engine()
    approval = engine.handle(_request(target_id="lab-a")).approval_request
    assert approval is not None
    _approve(store, approval)

    result = engine.handle(_request(target_id="lab-b"))

    assert result.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert provider.requests == []


def test_approval_cannot_be_reused_for_different_provider() -> None:
    base_engine, _provider, _sink, store = _engine()
    approval = base_engine.handle(_request()).approval_request
    assert approval is not None
    _approve(store, approval, provider_id="mock")
    other_engine, other_provider, _other_sink, _store = _engine(
        provider=OtherMockProvider(),
        store=store,
    )

    result = other_engine.handle(_request())

    assert result.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert other_provider.requests == []


def test_approval_cannot_approve_policy_audit_or_secret_hard_invariants() -> None:
    operator = Actor(type=ActorType.OPERATOR, id="operator-1")

    for capability_id in {
        "session.modify_policy",
        "session.disable_audit",
        "secrets.raw_reveal",
    }:
        with pytest.raises(ValueError, match="cannot be approval-resumed"):
            ApprovalGrant(
                request_id="approval-1",
                response_id="response-1",
                capability_id=capability_id,
                session_id="s1",
                target_id="lab-a",
                provider_id="mock",
                params_fingerprint="fingerprint",
                expires_at=NOW + timedelta(minutes=1),
                scope=ApprovalGrantScope.ONE_TIME,
                operator=operator,
            )


def test_expired_approval_fails_closed() -> None:
    engine, provider, _sink, store = _engine(now=NOW)
    request = _request()
    approval = engine.handle(request).approval_request
    assert approval is not None
    _approve(store, approval)
    expired_engine, _provider, _sink, _store = _engine(
        provider=provider,
        store=store,
        now=NOW + timedelta(minutes=16),
    )

    result = expired_engine.handle(request)

    assert result.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert provider.requests == []


def test_denied_approval_fails_closed() -> None:
    engine, provider, _sink, store = _engine()
    request = _request()
    approval = engine.handle(request).approval_request
    assert approval is not None
    denied = ApprovalResponse(
        id="response-denied",
        request_id=approval.id,
        outcome=ApprovalOutcome.DENIED,
        operator=Actor(type=ActorType.OPERATOR, id="operator-1"),
        decided_at=NOW,
    )

    with pytest.raises(ValueError, match="Only granted"):
        store.grant_from_response(
            request=approval,
            response=denied,
            provider_id="mock",
            parameters={},
        )

    result = engine.handle(request)

    assert result.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert provider.requests == []
