from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Mapping

import pytest

from agentickvm.control_plane import (
    ACTClearanceVerifier,
    Actor,
    ActorType,
    CapabilityRequest,
    ClearanceRequest,
    ClearanceResponse,
    ClearanceRiskFamily,
    ClearanceStatus,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    InMemoryAuditSink,
    MockACTClient,
    MockACTProofVerifier,
    cleared_response_for,
    mode_preset,
)
from agentickvm.providers.pikvm import (
    PIKVM_ACTUATION_CAPABILITIES,
    PiKVMObserveClient,
    PiKVMObserveProvider,
    default_pikvm_fake_transport,
)
from agentickvm.providers.pikvm_calibration import (
    PIKVM_ABSOLUTE_MAX,
    PiKVMScreenshotCalibration,
)
from agentickvm.providers.pikvm_transport import (
    PIKVM_ATX_POWER_CYCLE_PATH,
    PIKVM_HID_KEYBOARD_TYPE_PATH,
)


NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)
SESSION_ID = "session-1"


ACTUATION_CASES = (
    ("power.on", {}),
    ("power.force_off", {}),
    ("power.power_cycle", {"delay_seconds": 1}),
    ("power.reset", {}),
    ("input.keyboard_type", {"text": "password=synthetic-secret"}),
    ("input.mouse_move", {"x": 640, "y": 360, "screen_width": 1280, "screen_height": 720}),
    (
        "input.mouse_click",
        {"x": 320, "y": 180, "screen_width": 1280, "screen_height": 720, "button": "left"},
    ),
    ("media.mount_approved_iso", {"image_ref": "fixture-approved.iso"}),
)


class OneShotACTClient:
    """Mock ACT client that consumes one clearance and then returns pending."""

    def __init__(self) -> None:
        self.used = False

    def request_clearance(
        self,
        request: ClearanceRequest,
        *,
        timeout_seconds: int,
    ) -> ClearanceResponse:
        if self.used:
            return MockACTClient().request_clearance(request, timeout_seconds=timeout_seconds)
        self.used = True
        return cleared_response_for(request)

    def deny_clearance(
        self,
        request_id: str,
        *,
        reason: str,
        timeout_seconds: int,
    ) -> ClearanceResponse:
        return MockACTClient().deny_clearance(
            request_id,
            reason=reason,
            timeout_seconds=timeout_seconds,
        )


def _make_provider() -> tuple[PiKVMObserveProvider, PiKVMObserveClient]:
    client = PiKVMObserveClient(transport=default_pikvm_fake_transport())
    return PiKVMObserveProvider(enabled=True, client=client), client


def _control_plane(
    *,
    act_client,
    sink: InMemoryAuditSink | None = None,
    provider: PiKVMObserveProvider | None = None,
) -> tuple[ControlPlane, PiKVMObserveProvider, InMemoryAuditSink]:
    resolved_provider = provider
    if resolved_provider is None:
        resolved_provider, _ = _make_provider()
    resolved_sink = sink or InMemoryAuditSink()
    return (
        ControlPlane(
            policy=mode_preset(ControlMode.SUPERVISED),
            provider=resolved_provider,
            audit_sink=resolved_sink,
            now_factory=lambda: NOW,
            clearance_client=act_client,
            clearance_verifier=ACTClearanceVerifier(
                tower_id="mock-act",
                proof_verifier=MockACTProofVerifier(),
                test_mode=True,
            ),
        ),
        resolved_provider,
        resolved_sink,
    )


def _request(
    capability_id: str,
    *,
    target_id: str = "pikvm-host-a",
    params: Mapping[str, object] | None = None,
    request_id: str = "pikvm-clearance-1",
) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability_id,
        target_id=target_id,
        session_id=SESSION_ID,
        correlation_id=f"pikvm-actuation-{capability_id}",
        requester=Actor(type=ActorType.AGENT, id="agent"),
        intended_effect=f"exercise fixture {capability_id}",
        parameters=params or {},
        approval_request_id=request_id,
    )


@pytest.mark.parametrize(("capability_id", "params"), ACTUATION_CASES)
def test_pikvm_actuation_is_high_risk_and_requires_clearance(
    capability_id: str,
    params: Mapping[str, object],
) -> None:
    control_plane, provider, _sink = _control_plane(act_client=MockACTClient())
    assert capability_id in PIKVM_ACTUATION_CAPABILITIES

    result = control_plane.handle(_request(capability_id, params=params))

    assert result.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert result.clearance_request is not None
    assert result.clearance_request.risk_summary.risk_family == ClearanceRiskFamily.HIGH_RISK
    assert result.clearance_request.to_dict()["risk_family"] == "high_risk"
    assert provider.requests == []
    assert provider.client is not None
    assert provider.client.transport is not None
    assert provider.client.transport.calls == []


def test_mock_consumed_clearance_allows_pikvm_actuation_once() -> None:
    provider, client = _make_provider()
    control_plane, _provider_ref, _sink = _control_plane(
        act_client=OneShotACTClient(),
        provider=provider,
    )
    request = _request("power.power_cycle", params={"delay_seconds": 1})

    first = control_plane.handle(request)
    second = control_plane.handle(request)

    assert first.status == ControlPlaneStatus.COMPLETED
    assert second.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert [request.capability for request in provider.requests] == ["power.power_cycle"]
    assert client.transport is not None
    assert [call.path for call in client.transport.calls] == [PIKVM_ATX_POWER_CYCLE_PATH]


def test_clearance_for_action_params_cannot_authorize_different_params() -> None:
    probe, _probe_provider, _sink = _control_plane(act_client=MockACTClient())
    probe_result = probe.handle(
        _request(
            "input.keyboard_type",
            params={"text": "synthetic recovery command"},
            request_id="params-binding",
        )
    )
    clearance = probe_result.clearance_request
    assert clearance is not None
    mismatched_response = cleared_response_for(clearance)
    provider, client = _make_provider()
    control_plane, _provider_ref, _sink = _control_plane(
        act_client=MockACTClient(responses={clearance.request_id: mismatched_response}),
        provider=provider,
    )

    result = control_plane.handle(
        _request(
            "input.keyboard_type",
            params={"text": "different recovery command"},
            request_id=clearance.request_id,
        )
    )

    assert result.status == ControlPlaneStatus.DENIED
    assert result.message == "params_fingerprint mismatch"
    assert provider.requests == []
    assert client.transport is not None
    assert client.transport.calls == []


def test_clearance_for_host_a_cannot_authorize_host_b() -> None:
    probe, _probe_provider, _sink = _control_plane(act_client=MockACTClient())
    probe_result = probe.handle(
        _request(
            "power.power_cycle",
            target_id="pikvm-host-a",
            params={"delay_seconds": 1},
            request_id="target-binding",
        )
    )
    clearance = probe_result.clearance_request
    assert clearance is not None
    host_a_response = cleared_response_for(clearance)
    provider, client = _make_provider()
    control_plane, _provider_ref, _sink = _control_plane(
        act_client=MockACTClient(responses={clearance.request_id: host_a_response}),
        provider=provider,
    )

    result = control_plane.handle(
        _request(
            "power.power_cycle",
            target_id="pikvm-host-b",
            params={"delay_seconds": 1},
            request_id=clearance.request_id,
        )
    )

    assert result.status == ControlPlaneStatus.DENIED
    assert result.message == "target mismatch"
    assert provider.requests == []
    assert client.transport is not None
    assert client.transport.calls == []


def test_mismatched_clearance_capability_cannot_authorize_other_action() -> None:
    probe, _probe_provider, _sink = _control_plane(act_client=MockACTClient())
    probe_result = probe.handle(_request("power.power_cycle", request_id="action-binding"))
    clearance = probe_result.clearance_request
    assert clearance is not None
    mismatched = replace(cleared_response_for(clearance), capability="power.reset")
    provider, client = _make_provider()
    control_plane, _provider_ref, _sink = _control_plane(
        act_client=MockACTClient(responses={clearance.request_id: mismatched}),
        provider=provider,
    )

    result = control_plane.handle(_request("power.power_cycle", request_id=clearance.request_id))

    assert result.status == ControlPlaneStatus.DENIED
    assert result.message == "capability mismatch"
    assert provider.requests == []
    assert client.transport is not None
    assert client.transport.calls == []


def test_hid_typed_text_redacted_in_audit_and_results_by_default() -> None:
    secret_text = "password=synthetic-secret mfa=123456"
    sink = InMemoryAuditSink()
    control_plane, provider, _sink = _control_plane(
        act_client=MockACTClient(default_status=ClearanceStatus.CLEARED),
        sink=sink,
    )

    result = control_plane.handle(
        _request("input.keyboard_type", params={"text": secret_text}, request_id="hid-redaction")
    )

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    normalized = result.provider_result.normalized()
    assert normalized["data"]["parameters"]["text"] == "[REDACTED]"
    assert secret_text not in repr(normalized)
    assert secret_text not in repr([event.to_dict() for event in sink.events])
    assert provider.client is not None
    assert provider.client.transport is not None
    assert [call.path for call in provider.client.transport.calls] == [
        PIKVM_HID_KEYBOARD_TYPE_PATH
    ]


def test_pikvm_mouse_calibration_maps_screenshot_coordinates() -> None:
    calibration = PiKVMScreenshotCalibration(width=1280, height=720)

    assert calibration.map_point(x=0, y=0) == {"absolute_x": 0, "absolute_y": 0}
    assert calibration.map_point(x=1279, y=719) == {
        "absolute_x": PIKVM_ABSOLUTE_MAX,
        "absolute_y": PIKVM_ABSOLUTE_MAX,
    }
    assert calibration.map_point(x=640, y=360) == {
        "absolute_x": round(640 * PIKVM_ABSOLUTE_MAX / 1279),
        "absolute_y": round(360 * PIKVM_ABSOLUTE_MAX / 719),
    }
    assert calibration.map_point(x=-10, y=9999) == {
        "absolute_x": 0,
        "absolute_y": PIKVM_ABSOLUTE_MAX,
    }
