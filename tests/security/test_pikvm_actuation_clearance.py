"""Security coverage for clearance-gated PiKVM fixture actuation.

The PiKVM fixture provider exposes actuation capabilities (power, HID input,
media) so the ControlPlane clearance seam can be exercised without hardware.
These tests prove that:

* actuation never reaches the provider until ACT clearance is granted,
* a denied or mismatched clearance fails closed,
* cleared actuation runs only through the fake fixture transport and is always
  reported as *not* performed on hardware, and
* HID text is redacted before it can land in a result or audit record.

Nothing here contacts real hardware or opens a socket. This is mock-only QA.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from agentickvm.control_plane import (
    ACTClearanceVerifier,
    Actor,
    ActorType,
    CapabilityRequest,
    ClearanceStatus,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    InMemoryAuditSink,
    MockACTClient,
    MockACTProofVerifier,
    mode_preset,
)
from agentickvm.control_plane.act_client import cleared_response_for
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
from agentickvm.providers.pikvm_transport import FakePiKVMObserveTransport

NOW = datetime(2026, 6, 13, 12, 0, tzinfo=UTC)
TARGET = "pikvm-fixture-target"


def _provider() -> PiKVMObserveProvider:
    transport = default_pikvm_fake_transport()
    return PiKVMObserveProvider(
        provider_id="pikvm-fixture",
        enabled=True,
        client=PiKVMObserveClient(
            observe_transport=FakePiKVMObserveTransport(transport=transport)
        ),
    )


def _request(capability_id: str, *, parameters=None) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability_id,
        target_id=TARGET,
        session_id="session-1",
        correlation_id=f"pikvm-actuation-{capability_id}",
        requester=Actor(type=ActorType.AGENT, id="agent-1"),
        intended_effect=f"recover sacrificial fixture via {capability_id}",
        parameters=parameters or {},
        approval_request_id=f"clearance-{capability_id}",
    )


def _control_plane(
    *,
    act_client: MockACTClient,
    provider: PiKVMObserveProvider,
    audit_sink: InMemoryAuditSink | None = None,
) -> ControlPlane:
    return ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=provider,
        audit_sink=audit_sink or InMemoryAuditSink(),
        now_factory=lambda: NOW,
        clearance_client=act_client,
        clearance_verifier=ACTClearanceVerifier(
            tower_id="mock-act",
            proof_verifier=MockACTProofVerifier(),
            test_mode=True,
        ),
    )


def test_every_pikvm_actuation_capability_requires_act_clearance() -> None:
    for capability in sorted(PIKVM_ACTUATION_CAPABILITIES):
        provider = _provider()
        control_plane = _control_plane(act_client=MockACTClient(), provider=provider)

        result = control_plane.handle(_request(capability))

        assert result.status == ControlPlaneStatus.CLEARANCE_REQUIRED, capability
        assert result.clearance_request is not None, capability
        assert result.clearance_request.short_code, capability
        assert result.clearance_request.operator_message, capability
        # No actuation reaches the provider before clearance is granted.
        assert provider.requests == [], capability


def test_pikvm_power_actuation_runs_fixture_only_after_clearance() -> None:
    provider = _provider()
    act_client = MockACTClient(default_status=ClearanceStatus.CLEARED)
    control_plane = _control_plane(act_client=act_client, provider=provider)

    result = control_plane.handle(_request("power.on"))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    assert result.provider_result.performed_on_hardware is False
    assert result.provider_result.data["performed"] is False
    assert result.provider_result.data["fixture"] is True
    assert provider.requests[-1].capability == "power.on"


def test_pikvm_reset_actuation_denied_clearance_fails_closed() -> None:
    provider = _provider()
    act_client = MockACTClient(default_status=ClearanceStatus.DENIED)
    control_plane = _control_plane(act_client=act_client, provider=provider)

    result = control_plane.handle(_request("power.reset"))

    assert result.status == ControlPlaneStatus.DENIED
    assert provider.requests == []


def test_pikvm_actuation_target_mismatch_fails_closed() -> None:
    probe = _control_plane(
        act_client=MockACTClient(), provider=_provider()
    ).handle(_request("power.power_cycle"))
    clearance = probe.clearance_request
    assert clearance is not None
    mismatched = replace(cleared_response_for(clearance), target="other-target")
    provider = _provider()
    act_client = MockACTClient(responses={clearance.request_id: mismatched})
    control_plane = _control_plane(act_client=act_client, provider=provider)

    result = control_plane.handle(_request("power.power_cycle"))

    assert result.status == ControlPlaneStatus.DENIED
    assert result.message == "target mismatch"
    assert provider.requests == []


def test_pikvm_keyboard_actuation_redacts_typed_text_after_clearance() -> None:
    provider = _provider()
    act_client = MockACTClient(default_status=ClearanceStatus.CLEARED)
    control_plane = _control_plane(act_client=act_client, provider=provider)
    secret_text = "hunter2-not-a-real-password"

    result = control_plane.handle(
        _request("input.keyboard_type", parameters={"text": secret_text})
    )

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    assert result.provider_result.performed_on_hardware is False
    # The typed text must never survive into the result envelope or its repr.
    assert secret_text not in repr(result.provider_result)
    assert result.provider_result.data["parameters"]["text"] == "[REDACTED]"


def test_pikvm_mouse_actuation_runs_through_calibration_after_clearance() -> None:
    provider = _provider()
    act_client = MockACTClient(default_status=ClearanceStatus.CLEARED)
    control_plane = _control_plane(act_client=act_client, provider=provider)

    result = control_plane.handle(
        _request(
            "input.mouse_click",
            parameters={
                "x": 640,
                "y": 360,
                "screen_width": 1280,
                "screen_height": 720,
                "button": "left",
            },
        )
    )

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    assert result.provider_result.performed_on_hardware is False
    assert result.provider_result.data["performed"] is False


class TestScreenshotCalibration:
    """The mouse calibration is pure math and performs no IO."""

    def test_maps_origin_and_extent_to_absolute_range(self) -> None:
        calibration = PiKVMScreenshotCalibration(width=1280, height=720)

        assert calibration.map_point(x=0, y=0) == {"absolute_x": 0, "absolute_y": 0}
        bottom_right = calibration.map_point(x=1279, y=719)
        assert bottom_right == {
            "absolute_x": PIKVM_ABSOLUTE_MAX,
            "absolute_y": PIKVM_ABSOLUTE_MAX,
        }

    def test_clamps_out_of_range_points(self) -> None:
        calibration = PiKVMScreenshotCalibration(width=1280, height=720)

        clamped = calibration.map_point(x=10_000, y=-50)
        assert clamped["absolute_x"] == PIKVM_ABSOLUTE_MAX
        assert clamped["absolute_y"] == 0

    def test_rejects_degenerate_dimensions(self) -> None:
        with pytest.raises(ValueError):
            PiKVMScreenshotCalibration(width=1, height=720)
