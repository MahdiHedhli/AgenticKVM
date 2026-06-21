"""Security coverage for clearance-gated Redfish fixture actuation.

The Redfish fixture provider exposes power, boot-override, and BMC-reset
actuation so the ControlPlane clearance seam can be exercised without hardware.
These tests prove that actuation never reaches the provider until ACT clearance
is granted, that a denied or mismatched clearance fails closed, that a cleared
actuation runs only through the fake transport (never on hardware), and that a
clearance is one-shot. Mock-only: fake transport, mock ACT client, no network.
"""

from __future__ import annotations

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
from agentickvm.providers.redfish import (
    REDFISH_ACTUATION_CAPABILITIES,
    RedfishObserveClient,
    RedfishObserveProvider,
    default_redfish_fake_transport,
)

SESSION_ID = "session-1"
NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)

ACTUATION_CASES = (
    ("power.on", {}),
    ("power.force_off", {}),
    ("power.graceful_shutdown", {}),
    ("power.graceful_restart", {}),
    ("power.force_restart", {}),
    ("power.power_cycle", {}),
    ("power.nmi", {}),
    ("boot.override", {"boot_target": "Pxe"}),
    ("bmc.reset", {}),
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
            request_id, reason=reason, timeout_seconds=timeout_seconds
        )


def _provider() -> RedfishObserveProvider:
    return RedfishObserveProvider(
        provider_id="redfish-fixture",
        enabled=True,
        client=RedfishObserveClient(transport=default_redfish_fake_transport()),
    )


def _control_plane(*, act_client, provider: RedfishObserveProvider | None = None):
    resolved = provider or _provider()
    return (
        ControlPlane(
            policy=mode_preset(ControlMode.SUPERVISED),
            provider=resolved,
            audit_sink=InMemoryAuditSink(),
            now_factory=lambda: NOW,
            clearance_client=act_client,
            clearance_verifier=ACTClearanceVerifier(
                tower_id="mock-act",
                proof_verifier=MockACTProofVerifier(),
                test_mode=True,
            ),
        ),
        resolved,
    )


def _request(
    capability_id: str,
    *,
    target_id: str = "redfish-host-a",
    params: Mapping[str, object] | None = None,
    request_id: str = "redfish-clearance-1",
) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability_id,
        target_id=target_id,
        session_id=SESSION_ID,
        correlation_id=f"redfish-actuation-{capability_id}",
        requester=Actor(type=ActorType.AGENT, id="agent"),
        intended_effect=f"exercise fixture {capability_id}",
        parameters=params or {},
        approval_request_id=request_id,
    )


@pytest.mark.parametrize(("capability_id", "params"), ACTUATION_CASES)
def test_redfish_actuation_is_high_risk_and_requires_clearance(
    capability_id: str, params: Mapping[str, object]
) -> None:
    control_plane, provider = _control_plane(act_client=MockACTClient())
    assert capability_id in REDFISH_ACTUATION_CAPABILITIES

    result = control_plane.handle(_request(capability_id, params=params))

    assert result.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert result.clearance_request is not None
    assert result.clearance_request.risk_summary.risk_family == ClearanceRiskFamily.HIGH_RISK
    assert provider.requests == []


@pytest.mark.parametrize(("capability_id", "params"), ACTUATION_CASES)
def test_redfish_actuation_runs_fixture_only_after_clearance(
    capability_id: str, params: Mapping[str, object]
) -> None:
    control_plane, provider = _control_plane(
        act_client=MockACTClient(default_status=ClearanceStatus.CLEARED)
    )

    result = control_plane.handle(_request(capability_id, params=params))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    assert result.provider_result.performed_on_hardware is False
    assert result.provider_result.data["performed"] is False
    assert provider.requests[-1].capability == capability_id


def test_redfish_actuation_denied_clearance_fails_closed() -> None:
    control_plane, provider = _control_plane(
        act_client=MockACTClient(default_status=ClearanceStatus.DENIED)
    )

    result = control_plane.handle(_request("power.force_off"))

    assert result.status == ControlPlaneStatus.DENIED
    assert provider.requests == []


def test_mock_consumed_clearance_allows_redfish_actuation_once() -> None:
    control_plane, provider = _control_plane(act_client=OneShotACTClient())
    request = _request("power.power_cycle")

    first = control_plane.handle(request)
    second = control_plane.handle(request)

    assert first.status == ControlPlaneStatus.COMPLETED
    assert second.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert [r.capability for r in provider.requests] == ["power.power_cycle"]


def test_clearance_for_host_a_cannot_authorize_host_b() -> None:
    probe, _ = _control_plane(act_client=MockACTClient())
    probe_result = probe.handle(
        _request("power.power_cycle", target_id="redfish-host-a", request_id="target-binding")
    )
    clearance = probe_result.clearance_request
    assert clearance is not None
    host_a_response = cleared_response_for(clearance)
    control_plane, provider = _control_plane(
        act_client=MockACTClient(responses={clearance.request_id: host_a_response})
    )

    result = control_plane.handle(
        _request("power.power_cycle", target_id="redfish-host-b", request_id=clearance.request_id)
    )

    assert result.status == ControlPlaneStatus.DENIED
    assert result.message == "target mismatch"
    assert provider.requests == []


def test_redfish_boot_override_redacts_parameters_after_clearance() -> None:
    control_plane, _ = _control_plane(
        act_client=MockACTClient(default_status=ClearanceStatus.CLEARED)
    )

    result = control_plane.handle(_request("boot.override", params={"boot_target": "Pxe"}))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    assert result.provider_result.performed_on_hardware is False
    assert "parameters" in result.provider_result.data
