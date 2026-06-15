from __future__ import annotations

from datetime import UTC, datetime

from agentickvm.control_plane import (
    ACTClearanceVerifier,
    Actor,
    ActorType,
    Capability,
    CapabilityRequest,
    ClearanceRiskFamily,
    ClearanceStatus,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    InMemoryAuditSink,
    MockACTClient,
    MockACTProofVerifier,
    RiskLevel,
    clearance_risk_family_for_capability,
    mode_preset,
)
from agentickvm.control_plane.capabilities import DEFAULT_CAPABILITY_REGISTRY
from agentickvm.providers import MockProvider


NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)


def test_observe_capabilities_map_to_low_risk_family() -> None:
    capability = DEFAULT_CAPABILITY_REGISTRY.require("observe.status")

    assert clearance_risk_family_for_capability(capability) == ClearanceRiskFamily.LOW_RISK


def test_consequential_capabilities_map_to_high_risk_family() -> None:
    for capability_id in (
        "power.power_cycle",
        "power.force_restart",
        "input.keyboard_type",
        "media.mount_approved_iso",
        "boot.override",
    ):
        capability = DEFAULT_CAPABILITY_REGISTRY.require(capability_id)

        assert clearance_risk_family_for_capability(capability) == ClearanceRiskFamily.HIGH_RISK


def test_unmapped_capability_defaults_to_restrictive_high_risk_family() -> None:
    capability = Capability(
        id="runtime.unmapped_low_risk_fixture",
        family="runtime",
        action="unmapped_low_risk_fixture",
        title="Unmapped low-risk fixture",
        description="Fixture proving no permissive default exists.",
        risk=RiskLevel.LOW,
    )

    assert clearance_risk_family_for_capability(capability) == ClearanceRiskFamily.HIGH_RISK
    assert clearance_risk_family_for_capability(None) == ClearanceRiskFamily.HIGH_RISK


def test_clearance_request_carries_explicit_non_null_risk_family() -> None:
    act_client = MockACTClient()
    control_plane = ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=MockProvider(),
        audit_sink=InMemoryAuditSink(),
        now_factory=lambda: NOW,
        clearance_client=act_client,
        clearance_verifier=ACTClearanceVerifier(
            tower_id="mock-act",
            proof_verifier=MockACTProofVerifier(),
            test_mode=True,
        ),
    )

    result = control_plane.handle(
        CapabilityRequest(
            capability_id="input.keyboard_type",
            target_id="mock-host",
            session_id="session-1",
            correlation_id="risk-family-test",
            requester=Actor(type=ActorType.AGENT, id="agent"),
            intended_effect="type recovery command",
            parameters={"text": "synthetic command"},
            approval_request_id="risk-family-request",
        )
    )

    assert result.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert result.clearance_request is not None
    assert result.clearance_request.risk_summary.risk_family == ClearanceRiskFamily.HIGH_RISK
    assert result.clearance_request.to_dict()["risk_family"] == "high_risk"
