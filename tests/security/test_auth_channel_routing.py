"""Security coverage: the clearance step is routed by the selected auth channel.

mobile_signed (the recommended default) clears through ACT; local_terminal is a
selectable opt-out that clears through the local signed-grant broker even when an
ACT clearance client is wired. Either way the selection is recorded in the audit
trail and no provider executes before authorization.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentickvm.control_plane import (
    ACTClearanceVerifier,
    Actor,
    ActorType,
    AuditEventType,
    AuthChannel,
    CapabilityRequest,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    InMemoryAuditSink,
    MockACTClient,
    MockACTProofVerifier,
    mode_preset,
)
from agentickvm.providers import MockProvider

NOW = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)


class _TrackingACTClient:
    """Wrap MockACTClient to record whether ACT was consulted at all."""

    def __init__(self) -> None:
        self._inner = MockACTClient()
        self.request_calls = 0
        self.deny_calls = 0

    def request_clearance(self, request, *, timeout_seconds):
        self.request_calls += 1
        return self._inner.request_clearance(request, timeout_seconds=timeout_seconds)

    def deny_clearance(self, *args, **kwargs):
        self.deny_calls += 1
        return self._inner.deny_clearance(*args, **kwargs)


def _request() -> CapabilityRequest:
    return CapabilityRequest(
        capability_id="power.force_restart",
        target_id="mock-host",
        session_id="session-1",
        correlation_id="auth-channel-routing",
        requester=Actor(type=ActorType.AGENT, id="agent"),
        intended_effect="recover wedged mock fixture",
        parameters={"force": True},
        approval_request_id="clearance-1",
    )


def _control_plane(*, auth_channel, provider, audit_sink, act_client):
    return ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=provider,
        audit_sink=audit_sink,
        now_factory=lambda: NOW,
        clearance_client=act_client,
        clearance_verifier=ACTClearanceVerifier(
            tower_id="mock-act",
            proof_verifier=MockACTProofVerifier(),
            test_mode=True,
        ),
        auth_channel=auth_channel,
    )


def _approval_payloads(sink: InMemoryAuditSink) -> list[dict]:
    return [
        event.approval
        for event in sink.events
        if event.event_type == AuditEventType.APPROVAL_REQUESTED
    ]


def test_mobile_signed_routes_clearance_through_act() -> None:
    provider = MockProvider()
    sink = InMemoryAuditSink()
    control_plane = _control_plane(
        auth_channel=AuthChannel.MOBILE_SIGNED,
        provider=provider,
        audit_sink=sink,
        act_client=MockACTClient(),
    )

    result = control_plane.handle(_request())

    assert result.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert result.clearance_request is not None
    assert provider.requests == []

    payloads = _approval_payloads(sink)
    assert payloads, "expected an APPROVAL_REQUESTED audit event"
    channel = payloads[-1]["auth_channel"]
    assert channel["channel"] == "mobile_signed"
    assert channel["recommended"] is True
    assert channel["warning"] is None


def test_local_terminal_opt_out_routes_to_local_broker_even_with_act_client() -> None:
    provider = MockProvider()
    sink = InMemoryAuditSink()
    act_client = _TrackingACTClient()
    control_plane = _control_plane(
        auth_channel=AuthChannel.LOCAL_TERMINAL,
        provider=provider,
        audit_sink=sink,
        act_client=act_client,
    )

    result = control_plane.handle(_request())

    # local_terminal goes through the local broker, NOT ACT.
    assert result.status == ControlPlaneStatus.APPROVAL_REQUIRED
    assert result.clearance_request is None
    assert provider.requests == []
    assert act_client.request_calls == 0  # ACT client must not be consulted

    payloads = _approval_payloads(sink)
    assert payloads, "expected an APPROVAL_REQUESTED audit event"
    channel = payloads[-1]["auth_channel"]
    assert channel["channel"] == "local_terminal"
    assert channel["recommended"] is False
    assert "less secure" in channel["warning"]


def test_default_control_plane_channel_is_mobile_signed() -> None:
    control_plane = ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=MockProvider(),
        audit_sink=InMemoryAuditSink(),
    )

    assert control_plane.auth_channel == AuthChannel.MOBILE_SIGNED
    assert control_plane.auth_channel_selection.recommended is True
