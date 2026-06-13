from datetime import UTC, datetime, timedelta

from agentickvm.control_plane import (
    Actor,
    ActorType,
    ApprovalChannel,
    ApprovalGrantVerifier,
    CapabilityRequest,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    HMACDevelopmentSigner,
    InMemoryAuditSink,
    build_grant_payload,
    mode_preset,
)
from agentickvm.providers import MockProvider


NOW = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
PARAMS = {"force": True}


def _request(
    *,
    capability_id: str = "power.force_restart",
    approval_request_id: str | None = None,
    signed_grant=None,
    params=None,
) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability_id,
        target_id="mock-host",
        session_id="session-1",
        correlation_id="signed-grant-test",
        requester=Actor(type=ActorType.AGENT, id="agent"),
        intended_effect="recover wedged mock fixture",
        parameters=params if params is not None else PARAMS,
        approval_request_id=approval_request_id,
        signed_approval_grant=signed_grant,
    )


def _signer() -> HMACDevelopmentSigner:
    return HMACDevelopmentSigner(key_id="dev-key-1", secret=b"control-plane-secret")


def _signed_grant(
    *,
    request_id: str = "approval-1",
    capability: str = "power.force_restart",
    target: str = "mock-host",
    provider: str = "mock",
    params=None,
    expires_at=None,
):
    signer = _signer()
    payload = build_grant_payload(
        grant_id="grant-1",
        request_id=request_id,
        session_id="session-1",
        target=target,
        provider=provider,
        capability=capability,
        parameters=params if params is not None else PARAMS,
        risk_family=capability.split(".", 1)[0],
        channel=ApprovalChannel.OUT_OF_BAND,
        expires_at=expires_at or NOW + timedelta(minutes=5),
        signer_key_id=signer.key_id,
    )
    return signer.sign(payload)


def _control_plane(provider=None, sink=None) -> ControlPlane:
    signer = _signer()
    return ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=provider or MockProvider(),
        audit_sink=sink or InMemoryAuditSink(),
        now_factory=lambda: NOW,
        approval_grant_verifier=ApprovalGrantVerifier({signer.key_id: signer}),
    )


def test_valid_signed_grant_permits_matching_mock_action() -> None:
    provider = MockProvider()
    sink = InMemoryAuditSink()
    control_plane = _control_plane(provider=provider, sink=sink)
    grant = _signed_grant()

    result = control_plane.handle(
        _request(approval_request_id="approval-1", signed_grant=grant)
    )

    assert result.status == ControlPlaneStatus.COMPLETED
    assert provider.requests[-1].capability == "power.force_restart"
    assert "approval_verified" in [event.event_type.value for event in sink.events]
    assert "approval_consumed" in [event.event_type.value for event in sink.events]


def test_signed_grant_mismatch_returns_approval_required_without_execution() -> None:
    provider = MockProvider()
    sink = InMemoryAuditSink()
    control_plane = _control_plane(provider=provider, sink=sink)
    grant = _signed_grant(params={"force": False})

    result = control_plane.handle(
        _request(approval_request_id="approval-1", signed_grant=grant)
    )

    assert result.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert provider.requests == []
    assert "approval_rejected" in [event.event_type.value for event in sink.events]


def test_expired_signed_grant_returns_approval_required() -> None:
    provider = MockProvider()
    control_plane = _control_plane(provider=provider)
    grant = _signed_grant(expires_at=NOW - timedelta(seconds=1))

    result = control_plane.handle(
        _request(approval_request_id="approval-1", signed_grant=grant)
    )

    assert result.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert provider.requests == []


def test_one_time_signed_grant_cannot_be_reused_on_same_control_plane() -> None:
    provider = MockProvider()
    control_plane = _control_plane(provider=provider)
    grant = _signed_grant()

    first = control_plane.handle(
        _request(approval_request_id="approval-1", signed_grant=grant)
    )
    second = control_plane.handle(
        _request(approval_request_id="approval-1", signed_grant=grant)
    )

    assert first.status == ControlPlaneStatus.COMPLETED
    assert second.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert len(provider.requests) == 1


def test_signed_grant_cannot_approve_hard_invariant() -> None:
    provider = MockProvider()
    control_plane = _control_plane(provider=provider)
    grant = _signed_grant(
        capability="session.disable_audit",
        params={},
    )

    result = control_plane.handle(
        _request(
            capability_id="session.disable_audit",
            approval_request_id="approval-1",
            signed_grant=grant,
            params={},
        )
    )

    assert result.status == ControlPlaneStatus.DENIED
    assert result.message == "hard invariant"
    assert provider.requests == []
