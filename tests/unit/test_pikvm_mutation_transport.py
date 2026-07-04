"""Fixture tests for the socket-free PiKVM ATX live MUTATION transport seam.

Every collaborator is injected; no socket opens, no credential resolves, and
no mutating request can leave this process.
"""

from datetime import UTC, datetime, timedelta

import pytest

from agentickvm.control_plane.act_client import (
    ACTClearanceVerifier,
    MockACTProofVerifier,
    cleared_response_for,
)
from agentickvm.control_plane.clearance import build_clearance_request
from agentickvm.providers.errors import ProviderMutationBlockedError
from agentickvm.providers.mutation_gate import issue_verified_mutation_clearance
from agentickvm.providers.pikvm_mutation_transport import (
    LivePiKVMMutationTransport,
    PIKVM_LIVE_MUTATING_OPERATIONS,
)
from agentickvm.providers.pikvm_transport import (
    PIKVM_ATX_POWER_CYCLE_PATH,
    PIKVM_ATX_POWER_OFF_PATH,
    PIKVM_ATX_POWER_ON_PATH,
    PiKVMCredentialRef,
    PiKVMFingerprintMismatchError,
    PiKVMTargetConfig,
)

NOW = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
GOOD_FINGERPRINT = "cc" * 32
BAD_FINGERPRINT = "dd" * 32
TARGET_ID = "pikvm-node-fixture"
PROVIDER_ID = "pikvm-live-fixture"


class _StaticProbe:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint

    def certificate_der_sha256(self, *, host: str, port: int, timeout_seconds: float) -> str:
        return self.fingerprint


class FakeMutationClient:
    def __init__(self, trust) -> None:
        self.trust = trust
        self.posts = []

    def post_json(self, path, body, *, timeout_seconds):
        self.posts.append({"path": path, "body": dict(body)})
        return {"ok": True}


class RecordingMutationClientFactory:
    def __init__(self) -> None:
        self.calls = []
        self.clients: list[FakeMutationClient] = []

    def __call__(self, config, credential_ref, trust, clearance):
        self.calls.append({"trust": trust, "clearance": clearance})
        client = FakeMutationClient(trust)
        self.clients.append(client)
        return client


def _handle(*, capability: str, now: datetime = NOW):
    request = build_clearance_request(
        session_id="session-1",
        target=TARGET_ID,
        provider=PROVIDER_ID,
        capability=capability,
        parameters={},
        risk_family="high_risk",
        risk_summary="mutating ATX action",
        material_risks=("hardware power change",),
        intended_effect="exercise the pikvm mutation seam",
        requested_by="agent",
        audit_correlation_id="corr-pikvm-mutation",
        policy_context={},
        now=now,
    )
    return issue_verified_mutation_clearance(
        request=request,
        response=cleared_response_for(request),
        verifier=ACTClearanceVerifier(
            tower_id="mock-act",
            proof_verifier=MockACTProofVerifier(),
            test_mode=True,
        ),
        now=now,
    )


def _transport(
    *,
    factory=None,
    fingerprint: str | None = GOOD_FINGERPRINT,
    probe_fingerprint: str = GOOD_FINGERPRINT,
    now_factory=None,
) -> LivePiKVMMutationTransport:
    return LivePiKVMMutationTransport(
        config=PiKVMTargetConfig(
            base_url="https://pikvm.example.invalid",
            cert_fingerprint=fingerprint,
            verify_ssl=fingerprint is None,
        ),
        credential_ref=PiKVMCredentialRef("env://PIKVM_LAB"),
        target_id=TARGET_ID,
        provider_id=PROVIDER_ID,
        tls_probe=_StaticProbe(probe_fingerprint),
        http_client_factory=factory or RecordingMutationClientFactory(),
        now_factory=now_factory or (lambda: NOW),
    )


def test_mutating_operations_are_the_explicit_atx_power_set() -> None:
    assert PIKVM_LIVE_MUTATING_OPERATIONS == frozenset(
        {"power.on", "power.force_off", "power.power_cycle"}
    )


def test_transport_refuses_config_without_pinned_fingerprint() -> None:
    factory = RecordingMutationClientFactory()

    with pytest.raises(ProviderMutationBlockedError, match="pin"):
        _transport(factory=factory, fingerprint=None)

    assert factory.calls == []


def test_pin_preflight_mismatch_aborts_before_any_client_exists() -> None:
    factory = RecordingMutationClientFactory()

    with pytest.raises(PiKVMFingerprintMismatchError):
        _transport(factory=factory, probe_fingerprint=BAD_FINGERPRINT)

    assert factory.calls == []


@pytest.mark.parametrize(
    ("capability", "method", "path"),
    [
        ("power.on", "power_on", PIKVM_ATX_POWER_ON_PATH),
        ("power.force_off", "power_force_off", PIKVM_ATX_POWER_OFF_PATH),
        ("power.power_cycle", "power_cycle", PIKVM_ATX_POWER_CYCLE_PATH),
    ],
)
def test_atx_power_verbs_post_with_verified_clearance(
    capability: str, method: str, path: str
) -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)
    handle = _handle(capability=capability)

    result = getattr(transport, method)(clearance=handle)

    assert result["performed"] is True
    assert result["capability"] == capability
    assert factory.clients[-1].posts == [{"path": path, "body": {}}]
    assert factory.calls[-1]["clearance"] is handle


def test_mutating_verbs_refuse_without_clearance_handle() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)

    for call in (
        lambda: transport.power_on(clearance=None),
        lambda: transport.power_force_off(clearance=None),
        lambda: transport.power_cycle(clearance=None),
    ):
        with pytest.raises(ProviderMutationBlockedError):
            call()

    assert factory.calls == []


def test_capability_mismatched_handle_is_refused() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)
    handle = _handle(capability="power.on")

    with pytest.raises(ProviderMutationBlockedError):
        transport.power_cycle(clearance=handle)

    assert factory.calls == []


def test_handles_are_single_use_per_transport() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)
    handle = _handle(capability="power.on")

    transport.power_on(clearance=handle)
    with pytest.raises(ProviderMutationBlockedError, match="replay"):
        transport.power_on(clearance=handle)

    assert len(factory.calls) == 1


def test_expired_handle_is_refused_at_call_time() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(
        factory=factory, now_factory=lambda: NOW + timedelta(seconds=3600)
    )
    handle = _handle(capability="power.on")

    with pytest.raises(ProviderMutationBlockedError, match="expired"):
        transport.power_on(clearance=handle)

    assert factory.calls == []


def test_target_mismatched_handle_is_refused() -> None:
    factory = RecordingMutationClientFactory()
    transport = LivePiKVMMutationTransport(
        config=PiKVMTargetConfig(
            base_url="https://pikvm.example.invalid",
            cert_fingerprint=GOOD_FINGERPRINT,
        ),
        credential_ref=PiKVMCredentialRef("env://PIKVM_LAB"),
        target_id="different-target",
        provider_id=PROVIDER_ID,
        tls_probe=_StaticProbe(GOOD_FINGERPRINT),
        http_client_factory=factory,
        now_factory=lambda: NOW,
    )
    handle = _handle(capability="power.on")

    with pytest.raises(ProviderMutationBlockedError):
        transport.power_on(clearance=handle)

    assert factory.calls == []


def test_results_and_errors_never_leak_target_details() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)
    handle = _handle(capability="power.on")

    result = transport.power_on(clearance=handle)

    assert "pikvm.example.invalid" not in repr(result)
    with pytest.raises(ProviderMutationBlockedError) as excinfo:
        transport.power_on(clearance=handle)
    assert "pikvm.example.invalid" not in str(excinfo.value)
