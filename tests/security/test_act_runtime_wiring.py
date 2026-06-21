"""Wiring the real ACT clearance client from config into the runtime.

When the config carries a complete ``act`` section, build_runtime constructs the
real ACT HTTP clearance client and Ed25519 proof verifier behind the fail-closed
seam and turns on ACT-parity fingerprinting. With no ``act`` section the consume
seam stays fail-closed (no live ACT calls; local-broker path). No live network is
used: the transport is injected.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from agentickvm.config import build_runtime, config_from_mapping, load_config

ROOT = Path(__file__).resolve().parents[2]
from agentickvm.config.validation import ConfigValidationError
from agentickvm.control_plane import (
    ACTClearanceProofVerifier,
    ACTClearanceVerifier,
    ACTHTTPClearanceClient,
    Actor,
    ActorType,
    CapabilityRequest,
    ClearanceStatus,
    ControlMode,
    ControlPlane,
    ControlPlaneStatus,
    InMemoryAuditSink,
    MockACTClient,
    mode_preset,
    predicted_act_params_fingerprint,
)
from agentickvm.providers import MockProvider

TOWER_KEY = "OGpHYc-bD8rOc-IQfh8jWn6nO1gc3qpEvm8EbHXXWAc"

BASE_CONFIG = {
    "version": "0.1",
    "providers": [{"id": "mock", "type": "mock", "enabled": True}],
    "targets": [
        {
            "id": "mock-host",
            "provider": "mock",
            "enabled": True,
            "allowed_modes": ["Observe", "Supervised"],
        }
    ],
    "default_policy": {"mode": "Supervised"},
}

ACT_SECTION = {
    "gateway_url": "https://act.example.invalid/v1",
    "tower_id": "tower_test",
    "tower_keys": {"tower:tower_test": TOWER_KEY},
}


def _config(**overrides):
    raw = dict(BASE_CONFIG)
    raw.update(overrides)
    return config_from_mapping(raw)


class _FakeTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def post_json(self, path, body, *, timeout_seconds):
        self.calls.append(path)
        if path.endswith("approval_requested"):
            return {"approval_id": "appr-1", "state": "pending"}
        return {
            "contract_version": "act.clearance.v2",
            "request_id": "appr-1",
            "state": "pending",
            "session_id": "s1",
            "target": "mock-host",
            "provider": "mock",
            "capability": "power.force_restart",
            "params_fingerprint": "a" * 64,
            "risk_family": "external_effect",
            "short_code": "ABC123DEF0",
            "expires_at": "2026-06-18T12:00:00Z",
            "tower_id": "tower_test",
        }


def test_act_config_builds_real_client_and_verifier() -> None:
    runtime = build_runtime(_config(act=ACT_SECTION))

    assert isinstance(runtime.clearance_client, ACTHTTPClearanceClient)
    assert isinstance(runtime.clearance_verifier, ACTClearanceVerifier)
    assert isinstance(runtime.clearance_verifier.proof_verifier, ACTClearanceProofVerifier)
    assert runtime.act_parity_fingerprint is True


def test_example_act_config_is_a_valid_template() -> None:
    runtime = build_runtime(
        load_config(ROOT / "examples" / "config" / "act-clearance.yaml")
    )

    assert isinstance(runtime.clearance_client, ACTHTTPClearanceClient)
    assert isinstance(runtime.clearance_verifier, ACTClearanceVerifier)
    assert runtime.act_parity_fingerprint is True


def test_no_act_config_stays_fail_closed() -> None:
    runtime = build_runtime(_config())

    assert runtime.clearance_client is None
    assert runtime.clearance_verifier is None
    assert runtime.act_parity_fingerprint is False


def test_partial_act_config_is_not_configured() -> None:
    # gateway_url without tower_id/tower_keys must not build a live client.
    runtime = build_runtime(_config(act={"gateway_url": "https://act.example.invalid/v1"}))

    assert runtime.clearance_client is None
    assert runtime.act_parity_fingerprint is False


def test_invalid_act_section_rejected() -> None:
    with pytest.raises(ConfigValidationError, match="act"):
        config_from_mapping({**BASE_CONFIG, "act": "not-an-object"})
    with pytest.raises(ConfigValidationError, match="tower_keys"):
        config_from_mapping({**BASE_CONFIG, "act": {"tower_keys": "nope"}})


def test_injected_transport_avoids_live_network() -> None:
    transport = _FakeTransport()
    runtime = build_runtime(
        _config(act=ACT_SECTION), act_transport_factory=lambda url: transport
    )
    assert isinstance(runtime.clearance_client, ACTHTTPClearanceClient)

    # Drive the wired client through a real ControlPlane handle; the fake gateway
    # returns pending, so clearance is required and nothing executes.
    provider = MockProvider()
    control_plane = ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=provider,
        audit_sink=InMemoryAuditSink(),
        clearance_client=runtime.clearance_client,
        clearance_verifier=runtime.clearance_verifier,
        act_parity_fingerprint=runtime.act_parity_fingerprint,
    )

    result = control_plane.handle(
        CapabilityRequest(
            capability_id="power.force_restart",
            target_id="mock-host",
            session_id="s1",
            correlation_id="c1",
            requester=Actor(type=ActorType.AGENT, id="agent"),
            intended_effect="recover",
            parameters={"force": True},
            approval_request_id="appr-1",
        )
    )

    assert result.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert provider.requests == []
    assert transport.calls and transport.calls[0].endswith("approval_requested")


def test_engine_act_parity_produces_predictable_fingerprint() -> None:
    provider = MockProvider()
    control_plane = ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=provider,
        audit_sink=InMemoryAuditSink(),
        now_factory=lambda: datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
        clearance_client=MockACTClient(),  # pending
        clearance_verifier=ACTClearanceVerifier(tower_id="mock-act"),
        act_parity_fingerprint=True,
    )

    result = control_plane.handle(
        CapabilityRequest(
            capability_id="power.force_restart",
            target_id="mock-host",
            session_id="s1",
            correlation_id="c1",
            requester=Actor(type=ActorType.AGENT, id="agent"),
            intended_effect="recover",
            parameters={"force": True},
            approval_request_id="appr-1",
        )
    )

    assert result.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    clearance = result.clearance_request
    assert clearance is not None
    # The engine computed the fingerprint exactly as ACT will compute it.
    assert clearance.params_fingerprint == predicted_act_params_fingerprint(clearance)


def test_engine_without_act_parity_uses_local_fingerprint() -> None:
    provider = MockProvider()
    control_plane = ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=provider,
        audit_sink=InMemoryAuditSink(),
        now_factory=lambda: datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
        clearance_client=MockACTClient(),
        clearance_verifier=ACTClearanceVerifier(tower_id="mock-act"),
        act_parity_fingerprint=False,
    )

    result = control_plane.handle(
        CapabilityRequest(
            capability_id="power.force_restart",
            target_id="mock-host",
            session_id="s1",
            correlation_id="c1",
            requester=Actor(type=ActorType.AGENT, id="agent"),
            intended_effect="recover",
            parameters={"force": True},
            approval_request_id="appr-1",
        )
    )

    clearance = result.clearance_request
    assert clearance is not None
    # The local mirror fingerprint differs from ACT's authoritative computation.
    assert clearance.params_fingerprint != predicted_act_params_fingerprint(clearance)
