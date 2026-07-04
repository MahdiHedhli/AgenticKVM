"""THE clearance-chain smoke suite for the AgenticKVM beta contract.

One place that proves the whole chain — pair, request, ACT risk gating,
operator decision, Ed25519 clearance proof, aircraft-side verification,
fixture actuation, and audit on both sides — with the fail-closed matrix as
the point, not the happy path.

Two modes:

- default mode (CI): every fixture-backed row runs offline; gateway-dependent
  rows SKIP with a named reason.
- gateway-live mode: set ``AGENTICKVM_ACT_LIVE_GATEWAY_URL`` to a scratch
  Agentic Control Tower gateway on localhost (e.g. ``http://127.0.0.1:8905``)
  and the same rows run against a real converged tower: real pairing, real
  HMCP-signed operator decisions, real risk-family resolution, real Ed25519
  proofs, and real panic bulk-invalidation.

Hardware rows (real BMC / PiKVM actuation) are permanently skip-marked here
with the exact operator-run prerequisite; this suite never touches hardware.
"""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from act_live_gateway import (
    ConvergedTowerClearanceClient,
    GatewayOperator,
    live_gateway_api_base,
    live_tower_clearance_verifier,
    requires_live_gateway,
    utc_now,
)
from agentickvm.control_plane import (
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
from agentickvm.control_plane.act_client import ACTClearanceVerifier, cleared_response_for
from agentickvm.control_plane.act_http_client import ACTHTTPClearanceClient
from agentickvm.control_plane.act_proof import (
    ACTClearanceProofVerifier,
    TowerKeyRegistry,
)
from agentickvm.control_plane.clearance import (
    TOWER_RESOLVED_RISK_FAMILIES,
    ClearanceStatus,
    build_clearance_request,
    clearance_response_from_act_payload,
)
from agentickvm.live_validation.http_mutate import PinnedMutatingHTTPSJSONClient
from agentickvm.providers import MockProvider
from agentickvm.providers.errors import (
    ProviderMutationBlockedError,
    ProviderTLSVerificationError,
)
from agentickvm.providers.mutation_gate import (
    VerifiedMutationClearance,
    issue_verified_mutation_clearance,
)
from agentickvm.providers.pikvm_transport import sha256_fingerprint_for_der
from agentickvm.providers.redfish_mutation_transport import (
    LiveRedfishMutationTransport,
    REDFISH_LIVE_MUTATING_OPERATIONS,
)
from agentickvm.providers.redfish_transport import (
    RedfishCredentialRef,
    RedfishFingerprintMismatchError,
    RedfishTargetConfig,
)

# --------------------------------------------------------------------------- #
# Shared fixture-side constants
# --------------------------------------------------------------------------- #

NOW = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
TARGET_ID = "lab-node-fixture"
PROVIDER_ID = "redfish-live-fixture"
SYSTEM_PATH = "/redfish/v1/Systems/1"
GOOD_FINGERPRINT = "aa" * 32
BAD_FINGERPRINT = "bb" * 32

# Committed ACT proof vector (same vector the security tests pin): a real
# Ed25519 signature by the test tower key over the canonical proof string.
TOWER_PUBLIC_KEY_B64URL = "OGpHYc-bD8rOc-IQfh8jWn6nO1gc3qpEvm8EbHXXWAc"
VECTOR_PROOF = {
    "algorithm": "Ed25519",
    "canonicalization": "ACT-CLEARANCE-PROOF-V1",
    "key_id": "tower:tower_test",
    "signed_at": "2026-06-18T12:00:01Z",
    "fields": [
        "approval_id",
        "params_fingerprint",
        "short_code",
        "risk_family",
        "expires_at",
        "tower_id",
        "contract_version",
        "extensions_digest",
    ],
    "extensions_digest": "0" * 64,
    "signature": (
        "TVHXYcAhQTn8oh9uF-QPrn_7nmtNVakgT4JX9KDxh0stPBlGCI7uv9eXAlR4KrudzhkZJiFZKgzUFYCog-l5Cg"
    ),
}
VECTOR_EXPIRES_AT = "2026-06-18T12:00:00Z"
VECTOR_BEFORE_EXPIRY = datetime(2026, 6, 18, 11, 59, tzinfo=UTC)
VECTOR_AFTER_EXPIRY = datetime(2026, 6, 18, 12, 1, tzinfo=UTC)


def _vector_request():
    from agentickvm.control_plane.clearance import (
        ClearanceRequest,
        ClearanceRiskFamily,
        ClearanceRiskSummary,
    )

    return ClearanceRequest(
        request_id="appr_test_vector",
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        params_fingerprint="f" * 64,
        risk_summary=ClearanceRiskSummary(
            risk_family=ClearanceRiskFamily.HIGH_RISK, summary="forced restart"
        ),
        operator_message="Clearance ABC123DEF0 required for power.force_restart.",
        requested_by="agent",
        created_at=datetime(2026, 6, 18, 11, 58, tzinfo=UTC),
        expires_at=datetime(2026, 6, 18, 12, 0, tzinfo=UTC),
        short_code="ABC123DEF0",
        audit_correlation_id="corr-1",
    )


def _vector_payload(**overrides):
    payload = {
        "contract_version": "act.clearance.v1",
        "request_id": "appr_test_vector",
        "approval_id": "appr_test_vector",
        "state": "approved",
        "session_id": "session-1",
        "target": "mock-host",
        "provider": "mock",
        "capability": "power.force_restart",
        "params_fingerprint": "f" * 64,
        "risk_family": "external_effect",
        "short_code": "ABC123DEF0",
        "expires_at": VECTOR_EXPIRES_AT,
        "tower_id": "tower_test",
        "operator_message": "Clearance ABC123DEF0 approved.",
        "audit_correlation_id": "corr-1",
        "proof": dict(VECTOR_PROOF),
        "extensions": {"agentickvm": {"target": "mock-host", "provider": "mock"}},
    }
    payload.update(overrides)
    return payload


def _vector_verifier() -> ACTClearanceVerifier:
    registry = TowerKeyRegistry.from_b64url({"tower:tower_test": TOWER_PUBLIC_KEY_B64URL})
    return ACTClearanceVerifier(
        tower_id="tower_test",
        proof_verifier=ACTClearanceProofVerifier(registry=registry),
    )


def _mock_verifier() -> ACTClearanceVerifier:
    return ACTClearanceVerifier(
        tower_id="mock-act",
        proof_verifier=MockACTProofVerifier(),
        test_mode=True,
    )


def _capability_request(
    capability_id: str,
    *,
    session_id: str = "smoke-session-1",
    correlation_id: str | None = None,
    parameters: dict | None = None,
    approval_request_id: str | None = None,
) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability_id,
        target_id="smoke-target-a",
        session_id=session_id,
        correlation_id=correlation_id or f"corr-smoke-{capability_id}",
        requester=Actor(type=ActorType.AGENT, id="agent-smoke"),
        intended_effect="clearance-chain smoke coverage",
        parameters=parameters or {},
        approval_request_id=approval_request_id,
    )


def _offline_engine(*, act_client=None, provider=None, sink=None) -> tuple[ControlPlane, MockProvider, InMemoryAuditSink]:
    resolved_provider = provider or MockProvider()
    resolved_sink = sink or InMemoryAuditSink()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=resolved_provider,
        audit_sink=resolved_sink,
        clearance_client=act_client,
        clearance_verifier=_mock_verifier(),
        auth_channel=AuthChannel.MOBILE_SIGNED,
        now_factory=lambda: NOW,
    )
    return engine, resolved_provider, resolved_sink


def _mock_cleared_handle(*, capability: str, parameters: dict, now: datetime = NOW):
    request = build_clearance_request(
        session_id="smoke-session-1",
        target=TARGET_ID,
        provider=PROVIDER_ID,
        capability=capability,
        parameters=parameters,
        risk_family="high_risk",
        risk_summary="mutating fixture actuation",
        material_risks=("hardware state change",),
        intended_effect="clearance-chain smoke coverage",
        requested_by="agent-smoke",
        audit_correlation_id="corr-smoke-mutation",
        policy_context={},
        now=now,
    )
    return issue_verified_mutation_clearance(
        request=request,
        response=cleared_response_for(request),
        verifier=_mock_verifier(),
        now=now,
    )


class _StaticProbe:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint

    def certificate_der_sha256(self, *, host: str, port: int, timeout_seconds: float) -> str:
        return self.fingerprint


class _FakeMutationClient:
    def __init__(self, trust) -> None:
        self.trust = trust
        self.posts: list[dict] = []
        self.patches: list[dict] = []

    def post_json(self, path, body, *, timeout_seconds):
        self.posts.append({"path": path, "body": dict(body)})
        return {"TaskState": "Completed"}

    def patch_json(self, path, body, *, timeout_seconds):
        self.patches.append({"path": path, "body": dict(body)})
        return {"TaskState": "Completed"}


class _RecordingMutationClientFactory:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.clients: list[_FakeMutationClient] = []

    def __call__(self, config, credential_ref, trust, clearance):
        self.calls.append({"credential_ref": credential_ref, "clearance": clearance})
        client = _FakeMutationClient(trust)
        self.clients.append(client)
        return client


def _fixture_mutation_transport(
    *,
    factory: _RecordingMutationClientFactory | None = None,
    probe_fingerprint: str = GOOD_FINGERPRINT,
    now_factory=None,
) -> LiveRedfishMutationTransport:
    return LiveRedfishMutationTransport(
        config=RedfishTargetConfig(
            base_url="https://redfish.example.invalid",
            cert_fingerprint=GOOD_FINGERPRINT,
            verify_ssl=False,
        ),
        credential_ref=RedfishCredentialRef("env://REDFISH_SMOKE"),
        target_id=TARGET_ID,
        provider_id=PROVIDER_ID,
        system_path=SYSTEM_PATH,
        tls_probe=_StaticProbe(probe_fingerprint),
        http_client_factory=factory or _RecordingMutationClientFactory(),
        now_factory=now_factory or (lambda: NOW),
    )


class _RefusingACTTransport:
    """Transport stand-in for a dead gateway: every call is connection-refused."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def post_json(self, path, body, *, timeout_seconds):
        self.calls.append(path)
        raise OSError("connection refused")


# =========================================================================== #
# Happy paths on fixtures (default mode)
# =========================================================================== #


def test_offline_observe_read_path_end_to_end_on_fixture() -> None:
    """observe.* flows to the fixture provider with no clearance required."""

    engine, provider, sink = _offline_engine(act_client=MockACTClient())
    result = engine.handle(_capability_request("observe.power_state"))

    assert result.status == ControlPlaneStatus.COMPLETED
    assert result.provider_result is not None
    assert result.provider_result.performed_on_hardware is False
    assert provider.requests[-1].capability == "observe.power_state"
    event_types = [event.event_type for event in sink.events]
    assert AuditEventType.PROVIDER_EXECUTION_COMPLETED in event_types


def test_offline_mutating_path_end_to_end_on_fixture_transport() -> None:
    """A mock-cleared handle actuates exactly once on the fixture transport."""

    handle = _mock_cleared_handle(capability="power.on", parameters={})
    factory = _RecordingMutationClientFactory()
    transport = _fixture_mutation_transport(factory=factory)

    result = transport.power_on(clearance=handle)

    assert result["performed"] is True
    assert factory.clients[0].posts[0]["body"] == {"ResetType": "On"}
    assert factory.clients[0].posts[0]["path"].endswith("/Actions/ComputerSystem.Reset")


# =========================================================================== #
# Fail-closed matrix — fixture rows (default mode)
# =========================================================================== #


def test_missing_clearance_denied_before_any_transport_io() -> None:
    factory = _RecordingMutationClientFactory()
    transport = _fixture_mutation_transport(factory=factory)

    with pytest.raises(ProviderMutationBlockedError):
        transport.power_on(clearance=None)

    # No mutating client was ever built: no credentials, no bytes on the wire.
    assert factory.calls == []


def test_forged_clearance_handle_construction_refused() -> None:
    with pytest.raises(ProviderMutationBlockedError):
        VerifiedMutationClearance(
            request_id="req-forged",
            capability="power.on",
            target=TARGET_ID,
            provider=PROVIDER_ID,
            params_fingerprint="f" * 64,
            risk_family="external_effect",
            expires_at=NOW + timedelta(minutes=5),
            tower_id="tower_test",
            issued_at=NOW,
        )


def test_tampered_proof_bad_signature_rejected() -> None:
    proof = dict(VECTOR_PROOF)
    proof["signature"] = ("A" if proof["signature"][0] != "A" else "B") + proof["signature"][1:]
    response = clearance_response_from_act_payload(_vector_payload(proof=proof))

    result = _vector_verifier().verify(
        request=_vector_request(), response=response, now=VECTOR_BEFORE_EXPIRY
    )

    assert result.valid is False
    assert result.reason == "ACT clearance proof verification failed"
    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=_vector_request(),
            response=response,
            verifier=_vector_verifier(),
            now=VECTOR_BEFORE_EXPIRY,
        )


def test_tampered_proof_valid_signature_over_altered_fields_rejected() -> None:
    # The signature itself is the genuine tower vector; the response claims a
    # different (tower-resolved) risk family than the one the proof signed.
    response = clearance_response_from_act_payload(_vector_payload(risk_family="destructive"))

    result = _vector_verifier().verify(
        request=_vector_request(), response=response, now=VECTOR_BEFORE_EXPIRY
    )

    assert result.valid is False
    assert result.reason == "ACT clearance proof verification failed"

    # Same for an altered params fingerprint (the clearance "recipe").
    altered = clearance_response_from_act_payload(_vector_payload(params_fingerprint="a" * 64))
    result = _vector_verifier().verify(
        request=_vector_request(), response=altered, now=VECTOR_BEFORE_EXPIRY
    )
    assert result.valid is False


def test_expired_clearance_rejected_at_verification_time() -> None:
    response = clearance_response_from_act_payload(_vector_payload())

    result = _vector_verifier().verify(
        request=_vector_request(), response=response, now=VECTOR_AFTER_EXPIRY
    )

    assert result.valid is False
    assert result.status == ClearanceStatus.EXPIRED
    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=_vector_request(),
            response=response,
            verifier=_vector_verifier(),
            now=VECTOR_AFTER_EXPIRY,
        )


def test_expired_clearance_rejected_at_actuation_time() -> None:
    """A handle valid at issuance is refused when actuation happens too late."""

    handle = _mock_cleared_handle(capability="power.on", parameters={})
    factory = _RecordingMutationClientFactory()
    transport = _fixture_mutation_transport(
        factory=factory, now_factory=lambda: NOW + timedelta(minutes=10)
    )

    with pytest.raises(ProviderMutationBlockedError, match="expired"):
        transport.power_on(clearance=handle)
    assert factory.calls == []


def test_replayed_clearance_second_actuation_refused_by_single_use_ledger() -> None:
    handle = _mock_cleared_handle(capability="power.on", parameters={})
    factory = _RecordingMutationClientFactory()
    transport = _fixture_mutation_transport(factory=factory)

    assert transport.power_on(clearance=handle)["performed"] is True
    with pytest.raises(ProviderMutationBlockedError, match="single-use"):
        transport.power_on(clearance=handle)
    # Exactly one mutating client was ever built.
    assert len(factory.calls) == 1


def test_gateway_transport_failure_fails_closed_never_assumed_success() -> None:
    transport = _RefusingACTTransport()
    engine, provider, sink = _offline_engine(
        act_client=ACTHTTPClearanceClient(transport=transport)
    )

    result = engine.handle(_capability_request("power.force_restart"))

    assert result.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert result.clearance_response is not None
    assert result.clearance_response.status == ClearanceStatus.TOWER_UNAVAILABLE
    assert provider.requests == []
    event_types = [event.event_type for event in sink.events]
    assert AuditEventType.PROVIDER_EXECUTION_STARTED not in event_types


def test_cert_pin_mismatch_aborts_transport_preflight_before_credentials() -> None:
    """A pin mismatch refuses at construction; the client factory never runs."""

    factory = _RecordingMutationClientFactory()

    with pytest.raises(RedfishFingerprintMismatchError, match="credentials were not sent"):
        _fixture_mutation_transport(factory=factory, probe_fingerprint=BAD_FINGERPRINT)

    assert factory.calls == []


def test_cert_pin_mismatch_aborts_https_client_before_credential_bytes() -> None:
    """The pinned mutating HTTPS client checks the pin before sending anything."""

    presented_der = b"not-the-pinned-certificate"
    pinned_der = b"the-certificate-that-was-pinned"

    class _RecordingConnection:
        def __init__(self) -> None:
            self.requests: list[dict] = []
            self.sock = self

        def connect(self) -> None:
            pass

        def getpeercert(self, binary_form: bool = False) -> bytes:
            return presented_der

        def request(self, method, path, body=None, headers=None) -> None:
            self.requests.append({"method": method, "path": path})

        def getresponse(self):  # pragma: no cover - must never be reached
            raise AssertionError("request must never be sent on pin mismatch")

        def close(self) -> None:
            pass

    connection = _RecordingConnection()
    client = PinnedMutatingHTTPSJSONClient(
        host="redfish.example.invalid",
        port=443,
        headers={"Authorization": "credential-reference-material"},
        pinned_sha256=sha256_fingerprint_for_der(pinned_der),
        clearance=_mock_cleared_handle(capability="power.on", parameters={}),
        connection_factory=lambda host, port, context, timeout: connection,
        now_factory=lambda: NOW,
    )

    with pytest.raises(ProviderTLSVerificationError, match="credentials were not sent"):
        client.post_json("/redfish/v1/Systems/1/Actions/ComputerSystem.Reset", {}, timeout_seconds=2)

    assert connection.requests == []


def test_capability_over_assertion_clearance_for_x_refused_for_y() -> None:
    """A handle cleared for power.on cannot invoke power.force_off."""

    handle = _mock_cleared_handle(capability="power.on", parameters={})
    factory = _RecordingMutationClientFactory()
    transport = _fixture_mutation_transport(factory=factory)

    with pytest.raises(ProviderMutationBlockedError, match="capability mismatch"):
        transport.power_force_off(clearance=handle)
    assert factory.calls == []


def test_observe_clearance_cannot_mint_mutation_handle() -> None:
    request = build_clearance_request(
        session_id="smoke-session-1",
        target=TARGET_ID,
        provider=PROVIDER_ID,
        capability="observe.power_state",
        parameters={},
        risk_family="low_risk",
        risk_summary="read-only observation",
        material_risks=(),
        intended_effect="clearance-chain smoke coverage",
        requested_by="agent-smoke",
        audit_correlation_id="corr-smoke-observe",
        policy_context={},
        now=NOW,
    )

    with pytest.raises(ProviderMutationBlockedError, match="observe"):
        issue_verified_mutation_clearance(
            request=request,
            response=cleared_response_for(request),
            verifier=_mock_verifier(),
            now=NOW,
        )


def test_unknown_capability_fails_closed_not_silently_mapped() -> None:
    engine, provider, sink = _offline_engine(
        act_client=MockACTClient(default_status=ClearanceStatus.CLEARED)
    )

    result = engine.handle(_capability_request("power.melt_datacenter"))

    assert result.status == ControlPlaneStatus.DENIED
    assert result.message == "unknown capability"
    assert provider.requests == []
    event_types = [event.event_type for event in sink.events]
    assert AuditEventType.CAPABILITY_UNKNOWN_DENIED in event_types
    # And the live mutation layer implements only its explicit verb set.
    assert "power.melt_datacenter" not in REDFISH_LIVE_MUTATING_OPERATIONS


# =========================================================================== #
# Gateway-live rows (scratch converged tower on localhost)
# =========================================================================== #


@pytest.fixture(scope="module")
def operator() -> GatewayOperator:
    return GatewayOperator.pair(live_gateway_api_base())


def _live_engine(*, provider=None, sink=None) -> tuple[ControlPlane, MockProvider, InMemoryAuditSink]:
    resolved_provider = provider or MockProvider()
    resolved_sink = sink or InMemoryAuditSink()
    engine = ControlPlane(
        policy=mode_preset(ControlMode.SUPERVISED),
        provider=resolved_provider,
        audit_sink=resolved_sink,
        clearance_client=ConvergedTowerClearanceClient(live_gateway_api_base()),
        clearance_verifier=live_tower_clearance_verifier(),
        auth_channel=AuthChannel.MOBILE_SIGNED,
        act_parity_fingerprint=True,
    )
    return engine, resolved_provider, resolved_sink


def _smoke_session(label: str) -> str:
    return f"smoke-{label}-{uuid4().hex[:12]}"


def _live_mirror_request(
    *,
    capability: str,
    session_id: str,
    correlation_id: str,
    request_id: str | None = None,
    parameters: dict | None = None,
):
    return build_clearance_request(
        session_id=session_id,
        target=TARGET_ID,
        provider=PROVIDER_ID,
        capability=capability,
        parameters=parameters or {},
        risk_family="high_risk",
        risk_summary="mutating fixture actuation",
        material_risks=("hardware state change",),
        intended_effect="clearance-chain smoke coverage",
        requested_by="agent-smoke",
        audit_correlation_id=correlation_id,
        policy_context={},
        now=utc_now(),
        request_id=request_id,
        act_parity=True,
    )


def _live_cleared_response(operator: GatewayOperator, *, capability: str, session_id: str, correlation_id: str):
    """Drive one full live clearance: request -> operator approval -> cleared."""

    client = ConvergedTowerClearanceClient(live_gateway_api_base())
    fresh = _live_mirror_request(
        capability=capability, session_id=session_id, correlation_id=correlation_id
    )
    pending = client.request_clearance(fresh, timeout_seconds=20)
    assert pending.status == ClearanceStatus.CLEARANCE_REQUIRED, pending.reason
    approval_id = pending.request_id
    operator.approve_once(approval_id)
    resumed = _live_mirror_request(
        capability=capability,
        session_id=session_id,
        correlation_id=correlation_id,
        request_id=approval_id,
    )
    response = client.request_clearance(resumed, timeout_seconds=20)
    assert response.status == ClearanceStatus.CLEARED, response.reason
    return resumed, response


@requires_live_gateway
def test_live_happy_path_pair_gate_decide_prove_verify_actuate_audit(operator) -> None:
    """The one happy path: full clearance chain against a real tower.

    pair -> capability request -> tower risk-family gating -> HMCP-signed
    operator decision -> Ed25519 clearance proof -> strict aircraft-side
    verification -> fixture actuation -> audit entries on both sides.
    """

    session_id = _smoke_session("happy")
    correlation_id = f"corr-{session_id}"
    engine, provider, sink = _live_engine()
    request = _capability_request(
        "power.force_restart",
        session_id=session_id,
        correlation_id=correlation_id,
        parameters={"reason": "clearance-chain smoke"},
    )

    # Leg 1: the tower gates the capability behind a pending clearance.
    leg1 = engine.handle(request)
    assert leg1.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert provider.requests == []
    approval_id = leg1.clearance_response.request_id
    assert approval_id and approval_id != leg1.clearance_request.request_id
    # ACT owns risk-family resolution: the tower answered with a resolved
    # act.clearance.v2 family, not the aircraft's coarse label.
    assert leg1.clearance_response.risk_family in TOWER_RESOLVED_RISK_FAMILIES

    # Operator decision through the paired, HMCP-signed mobile channel.
    decision = operator.approve_once(approval_id)
    assert decision["state"] == "approved"

    # Leg 2: resume with the tower-issued clearance id; the aircraft verifies
    # the Ed25519 proof + fingerprint parity and actuates on the fixture.
    leg2 = engine.handle(replace(request, approval_request_id=approval_id))
    assert leg2.status == ControlPlaneStatus.COMPLETED, leg2.message
    assert leg2.provider_result is not None
    assert leg2.provider_result.performed_on_hardware is False
    assert provider.requests[-1].capability == "power.force_restart"

    # Audit on the aircraft side.
    event_types = [event.event_type for event in sink.events]
    assert AuditEventType.APPROVAL_REQUESTED in event_types
    assert AuditEventType.APPROVAL_VERIFIED in event_types
    assert AuditEventType.PROVIDER_EXECUTION_COMPLETED in event_types

    # Audit on the tower side.
    requested = operator.audit_events("approval_requested")
    assert any(event.get("approval_id") == approval_id for event in requested)
    decided = operator.audit_events("approval_decision")
    assert any(event.get("approval_id") == approval_id for event in decided)


@requires_live_gateway
def test_live_mutating_fixture_transport_actuates_with_tower_issued_proof(operator) -> None:
    """A live tower proof mints a handle that drives the mutating transport."""

    session_id = _smoke_session("mutate")
    request, response = _live_cleared_response(
        operator,
        capability="power.on",
        session_id=session_id,
        correlation_id=f"corr-{session_id}",
    )
    verifier = live_tower_clearance_verifier()
    verification = verifier.verify(request=request, response=response, now=utc_now())
    assert verification.valid, verification.reason

    handle = issue_verified_mutation_clearance(
        request=request,
        response=response,
        verifier=verifier,
        now=utc_now(),
        parameters={},
    )
    factory = _RecordingMutationClientFactory()
    transport = _fixture_mutation_transport(factory=factory, now_factory=utc_now)

    result = transport.power_on(clearance=handle)

    assert result["performed"] is True
    assert factory.clients[0].posts[0]["body"] == {"ResetType": "On"}


@requires_live_gateway
def test_live_pending_clearance_blocks_actuation_until_decision(operator) -> None:
    session_id = _smoke_session("pending")
    engine, provider, _ = _live_engine()

    result = engine.handle(
        _capability_request(
            "power.force_restart",
            session_id=session_id,
            correlation_id=f"corr-{session_id}",
        )
    )

    assert result.status == ControlPlaneStatus.CLEARANCE_REQUIRED
    assert result.clearance_response.status == ClearanceStatus.CLEARANCE_REQUIRED
    assert provider.requests == []


@requires_live_gateway
def test_live_denied_clearance_fails_closed(operator) -> None:
    session_id = _smoke_session("denied")
    correlation_id = f"corr-{session_id}"
    engine, provider, _ = _live_engine()
    request = _capability_request(
        "power.force_restart", session_id=session_id, correlation_id=correlation_id
    )

    leg1 = engine.handle(request)
    approval_id = leg1.clearance_response.request_id
    operator.deny(approval_id)

    leg2 = engine.handle(replace(request, approval_request_id=approval_id))

    assert leg2.status == ControlPlaneStatus.DENIED
    assert provider.requests == []


@requires_live_gateway
def test_live_expired_clearance_rejected(operator) -> None:
    session_id = _smoke_session("expired")
    correlation_id = f"corr-{session_id}"
    client = ConvergedTowerClearanceClient(live_gateway_api_base())

    # Approved, then expired: the aircraft's expiry check refuses at verify time.
    short_lived = build_clearance_request(
        session_id=session_id,
        target=TARGET_ID,
        provider=PROVIDER_ID,
        capability="power.on",
        parameters={},
        risk_family="high_risk",
        risk_summary="mutating fixture actuation",
        material_risks=("hardware state change",),
        intended_effect="clearance-chain smoke coverage",
        requested_by="agent-smoke",
        audit_correlation_id=correlation_id,
        policy_context={},
        now=utc_now(),
        ttl_seconds=1,
        act_parity=True,
    )
    pending = client.request_clearance(short_lived, timeout_seconds=20)
    approval_id = pending.request_id
    operator.approve_once(approval_id)
    time.sleep(1.5)
    resumed = _live_mirror_request(
        capability="power.on",
        session_id=session_id,
        correlation_id=correlation_id,
        request_id=approval_id,
    )
    response = client.request_clearance(resumed, timeout_seconds=20)
    verification = live_tower_clearance_verifier().verify(
        request=resumed, response=response, now=utc_now()
    )
    assert verification.valid is False
    assert verification.status in (ClearanceStatus.EXPIRED, ClearanceStatus.DENIED)
    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=resumed,
            response=response,
            verifier=live_tower_clearance_verifier(),
            now=utc_now(),
            parameters={},
        )

    # Pending and never decided: the tower itself expires the clearance.
    abandoned = build_clearance_request(
        session_id=session_id,
        target=TARGET_ID,
        provider=PROVIDER_ID,
        capability="power.on",
        parameters={},
        risk_family="high_risk",
        risk_summary="mutating fixture actuation",
        material_risks=("hardware state change",),
        intended_effect="clearance-chain smoke coverage",
        requested_by="agent-smoke",
        audit_correlation_id=f"{correlation_id}-abandoned",
        policy_context={},
        now=utc_now(),
        ttl_seconds=1,
        act_parity=True,
    )
    pending = client.request_clearance(abandoned, timeout_seconds=20)
    time.sleep(1.5)
    later = client.request_clearance(
        _live_mirror_request(
            capability="power.on",
            session_id=session_id,
            correlation_id=f"{correlation_id}-abandoned",
            request_id=pending.request_id,
        ),
        timeout_seconds=20,
    )
    assert later.status == ClearanceStatus.EXPIRED


@requires_live_gateway
def test_live_replayed_clearance_second_actuation_refused(operator) -> None:
    session_id = _smoke_session("replay")
    request, response = _live_cleared_response(
        operator,
        capability="power.on",
        session_id=session_id,
        correlation_id=f"corr-{session_id}",
    )
    verifier = live_tower_clearance_verifier()
    handle = issue_verified_mutation_clearance(
        request=request, response=response, verifier=verifier, now=utc_now(), parameters={}
    )
    factory = _RecordingMutationClientFactory()
    transport = _fixture_mutation_transport(factory=factory, now_factory=utc_now)

    assert transport.power_on(clearance=handle)["performed"] is True
    with pytest.raises(ProviderMutationBlockedError, match="single-use"):
        transport.power_on(clearance=handle)
    assert len(factory.calls) == 1


@requires_live_gateway
def test_live_tampered_proof_bad_signature_rejected(operator) -> None:
    session_id = _smoke_session("tamper-sig")
    request, _ = _live_cleared_response(
        operator,
        capability="power.on",
        session_id=session_id,
        correlation_id=f"corr-{session_id}",
    )
    # Re-poll the raw payload and corrupt the signature in transit.
    client = ConvergedTowerClearanceClient(live_gateway_api_base())
    payload = dict(client.poll_raw(request.request_id, timeout_seconds=20))
    proof = dict(payload["proof"])
    signature = str(proof["signature"])
    proof["signature"] = ("A" if signature[0] != "A" else "B") + signature[1:]
    payload["proof"] = proof
    response = clearance_response_from_act_payload(payload)

    verification = live_tower_clearance_verifier().verify(
        request=request, response=response, now=utc_now()
    )

    assert verification.valid is False
    assert verification.reason == "ACT clearance proof verification failed"


@requires_live_gateway
def test_live_tampered_proof_valid_signature_over_altered_fields_rejected(operator) -> None:
    session_id = _smoke_session("tamper-fields")
    request, _ = _live_cleared_response(
        operator,
        capability="power.on",
        session_id=session_id,
        correlation_id=f"corr-{session_id}",
    )
    client = ConvergedTowerClearanceClient(live_gateway_api_base())
    payload = dict(client.poll_raw(request.request_id, timeout_seconds=20))
    # The proof signature is the genuine tower signature; the response now
    # claims a different resolved risk family than the one the tower signed.
    payload["risk_family"] = "routine"
    response = clearance_response_from_act_payload(payload)

    verification = live_tower_clearance_verifier().verify(
        request=request, response=response, now=utc_now()
    )

    assert verification.valid is False
    assert verification.reason == "ACT clearance proof verification failed"


@requires_live_gateway
def test_live_panic_bulk_invalidates_pending_and_approved_clearances(operator) -> None:
    """Emergency stop mid-session kills every unconsumed clearance on the tower."""

    session_id = _smoke_session("panic")
    correlation_id = f"corr-{session_id}"
    client = ConvergedTowerClearanceClient(live_gateway_api_base())

    # One approved-but-unconsumed clearance and one still-pending clearance.
    approved_request = _live_mirror_request(
        capability="power.on", session_id=session_id, correlation_id=correlation_id
    )
    approved_pending = client.request_clearance(approved_request, timeout_seconds=20)
    approved_id = approved_pending.request_id
    operator.approve_once(approved_id)

    pending_request = _live_mirror_request(
        capability="power.force_off",
        session_id=session_id,
        correlation_id=f"{correlation_id}-pending",
    )
    still_pending = client.request_clearance(pending_request, timeout_seconds=20)
    pending_id = still_pending.request_id

    # Panic.
    intervention = operator.emergency_stop(session_id, reason="clearance-chain smoke panic")
    assert intervention["resulting_state"] == "approvals_invalidated"

    # Subsequent proof fetches are denied for both clearances...
    for approval_id, capability, corr in (
        (approved_id, "power.on", correlation_id),
        (pending_id, "power.force_off", f"{correlation_id}-pending"),
    ):
        resumed = _live_mirror_request(
            capability=capability,
            session_id=session_id,
            correlation_id=corr,
            request_id=approval_id,
        )
        response = client.request_clearance(resumed, timeout_seconds=20)
        assert response.status == ClearanceStatus.DENIED
        # ... and actuation can never be minted from them.
        with pytest.raises(ProviderMutationBlockedError):
            issue_verified_mutation_clearance(
                request=resumed,
                response=response,
                verifier=live_tower_clearance_verifier(),
                now=utc_now(),
                parameters={},
            )


@requires_live_gateway
def test_live_capability_over_assertion_refused(operator) -> None:
    """A clearance issued for capability X cannot authorize capability Y."""

    session_id = _smoke_session("overassert")
    correlation_id = f"corr-{session_id}"
    request, response = _live_cleared_response(
        operator, capability="power.on", session_id=session_id, correlation_id=correlation_id
    )
    verifier = live_tower_clearance_verifier()

    # Asserting the cleared response against a mirror request for a different
    # capability fails verification outright.
    over_asserted = _live_mirror_request(
        capability="power.force_off",
        session_id=session_id,
        correlation_id=correlation_id,
        request_id=request.request_id,
    )
    verification = verifier.verify(request=over_asserted, response=response, now=utc_now())
    assert verification.valid is False
    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=over_asserted,
            response=response,
            verifier=verifier,
            now=utc_now(),
            parameters={},
        )

    # And a genuine handle for X is refused when used to invoke Y.
    handle = issue_verified_mutation_clearance(
        request=request, response=response, verifier=verifier, now=utc_now(), parameters={}
    )
    factory = _RecordingMutationClientFactory()
    transport = _fixture_mutation_transport(factory=factory, now_factory=utc_now)
    with pytest.raises(ProviderMutationBlockedError, match="capability mismatch"):
        transport.power_force_off(clearance=handle)
    assert factory.calls == []


@requires_live_gateway
def test_live_gateway_connection_refused_fails_closed(operator) -> None:
    """A dead gateway yields TOWER_UNAVAILABLE, never assumed success."""

    # Port 1 on loopback: connection refused without leaving the machine.
    dead_client = ConvergedTowerClearanceClient("http://127.0.0.1:1/v1")
    session_id = _smoke_session("dead")
    request = _live_mirror_request(
        capability="power.on", session_id=session_id, correlation_id=f"corr-{session_id}"
    )

    response = dead_client.request_clearance(request, timeout_seconds=2)

    assert response.status == ClearanceStatus.TOWER_UNAVAILABLE
    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=request,
            response=response,
            verifier=live_tower_clearance_verifier(),
            now=utc_now(),
            parameters={},
        )


@requires_live_gateway
def test_live_production_hermes_seam_request_leg_and_fail_closed_invariant(operator) -> None:
    """The shipped hermes-seam client files real clearances and never yields an
    unverified mutation handle.

    The converged tower's hermes adapter is lossy today (it does not persist
    the aircraft extensions envelope), so strict verification of a clearance
    created through it may fail on fingerprint parity. The contract this test
    pins is fail-closed either way: a cleared-but-unverifiable response can
    never mint a mutation handle, and a verifiable one binds the capability.
    """

    from agentickvm.control_plane.act_http_client import UrllibACTHTTPTransport

    session_id = _smoke_session("hermes")
    transport = UrllibACTHTTPTransport(base_url=live_gateway_api_base())
    production_client = ACTHTTPClearanceClient(transport=transport)
    request = _live_mirror_request(
        capability="power.on", session_id=session_id, correlation_id=f"corr-{session_id}"
    )

    pending = production_client.request_clearance(request, timeout_seconds=20)

    # The request leg is accepted by the published gateway schema and the
    # tower answers with a real pending clearance under its own approval id.
    assert pending.status == ClearanceStatus.CLEARANCE_REQUIRED, pending.reason
    approval_id = pending.request_id
    assert approval_id and approval_id != request.request_id

    operator.approve_once(approval_id)
    payload = transport.post_json(
        "/hermes/tools/approval_status", {"approval_id": approval_id}, timeout_seconds=20
    )
    response = clearance_response_from_act_payload(payload)
    assert response.status == ClearanceStatus.CLEARED
    assert response.proof is not None

    resumed = _live_mirror_request(
        capability="power.on",
        session_id=session_id,
        correlation_id=f"corr-{session_id}",
        request_id=approval_id,
    )
    verifier = live_tower_clearance_verifier()
    verification = verifier.verify(request=resumed, response=response, now=utc_now())
    if verification.valid:
        handle = issue_verified_mutation_clearance(
            request=resumed, response=response, verifier=verifier, now=utc_now(), parameters={}
        )
        assert handle.capability == "power.on"
    else:
        with pytest.raises(ProviderMutationBlockedError):
            issue_verified_mutation_clearance(
                request=resumed,
                response=response,
                verifier=verifier,
                now=utc_now(),
                parameters={},
            )


# =========================================================================== #
# Hardware rows — operator-run only, never automated here
# =========================================================================== #


@pytest.mark.skip(
    reason=(
        "requires a live Supermicro BMC + valid Redfish web credentials — "
        "operator-run read-only validation pass (agentickvm.live_validation.redfish); "
        "no hardware is reachable from the automated suite"
    )
)
def test_live_hardware_redfish_read_only_pass_requires_supermicro_bmc() -> None:
    raise AssertionError("operator-run only")


@pytest.mark.skip(
    reason=(
        "requires a sacrificial NanoKVM/PiKVM target + operator supervision — "
        "mutating actuation (power/ATX/boot override) is never automated; "
        "operator-run via agentickvm.live_validation.{redfish,pikvm}_mutate"
    )
)
def test_live_hardware_mutating_actuation_requires_sacrificial_kvm_target() -> None:
    raise AssertionError("operator-run only")
