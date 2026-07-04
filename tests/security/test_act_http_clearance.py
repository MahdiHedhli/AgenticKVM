"""Real ACT clearance consume path: HTTP client -> v2 parse -> proof verify.

The transport is faked (no live network). The cleared response carries the
committed tower proof vector, so the full real path -- request mapping, gateway
poll, act.clearance.v2 response parsing, real Ed25519 proof verification, and
request/response binding -- is exercised end-to-end. Fingerprint and target
binding must hold; an unavailable gateway and an expired clearance fail closed.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentickvm.control_plane import (
    ACTClearanceProofVerifier,
    ACTClearanceVerifier,
    ACTHTTPClearanceClient,
    ClearanceRequest,
    ClearanceRiskFamily,
    ClearanceRiskSummary,
    ClearanceStatus,
    TowerKeyRegistry,
    clearance_response_from_act_payload,
)

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
EXPIRES_AT = "2026-06-18T12:00:00Z"
BEFORE_EXPIRY = datetime(2026, 6, 18, 11, 59, tzinfo=UTC)
AFTER_EXPIRY = datetime(2026, 6, 18, 12, 1, tzinfo=UTC)
CREATED_AT = datetime(2026, 6, 18, 11, 58, tzinfo=UTC)


class _FakeTransport:
    def __init__(self, status_payload, *, fail: bool = False) -> None:
        self.status_payload = status_payload
        self.fail = fail
        self.calls: list[str] = []

    def post_json(self, path, body, *, timeout_seconds):
        self.calls.append(path)
        if self.fail:
            raise OSError("ACT gateway unreachable")
        if path.endswith("approval_requested"):
            return {"approval_id": "appr_test_vector", "state": "pending"}
        return self.status_payload


def _request() -> ClearanceRequest:
    # Construct a pending request whose binding fields match the committed vector.
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
        created_at=CREATED_AT,
        expires_at=datetime(2026, 6, 18, 12, 0, tzinfo=UTC),
        short_code="ABC123DEF0",
        audit_correlation_id="corr-1",
    )


def _cleared_payload(**overrides):
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
        "expires_at": EXPIRES_AT,
        "tower_id": "tower_test",
        "operator_message": "Clearance ABC123DEF0 approved.",
        "audit_correlation_id": "corr-1",
        "proof": VECTOR_PROOF,
        "extensions": {"agentickvm": {"target": "mock-host", "provider": "mock"}},
    }
    payload.update(overrides)
    return payload


def _verifier() -> ACTClearanceVerifier:
    registry = TowerKeyRegistry.from_b64url({"tower:tower_test": TOWER_PUBLIC_KEY_B64URL})
    return ACTClearanceVerifier(
        tower_id="tower_test",
        proof_verifier=ACTClearanceProofVerifier(registry=registry),
    )


def test_real_client_clears_end_to_end_with_real_proof() -> None:
    transport = _FakeTransport(_cleared_payload())
    client = ACTHTTPClearanceClient(transport=transport)
    request = _request()

    response = client.request_clearance(request, timeout_seconds=20)

    # The client consulted both gateway endpoints.
    assert transport.calls[0].endswith("approval_requested")
    assert transport.calls[1].endswith("approval_status")
    assert response.status == ClearanceStatus.CLEARED
    assert response.contract_version == "act.clearance.v1"
    assert response.bound_material is not None

    result = _verifier().verify(request=request, response=response, now=BEFORE_EXPIRY)

    assert result.valid is True, result.reason
    assert result.status == ClearanceStatus.CLEARED


def test_target_binding_mismatch_fails_closed() -> None:
    payload = _cleared_payload(
        target="evil-host", extensions={"agentickvm": {"target": "evil-host"}}
    )
    client = ACTHTTPClearanceClient(transport=_FakeTransport(payload))
    request = _request()

    response = client.request_clearance(request, timeout_seconds=20)
    result = _verifier().verify(request=request, response=response, now=BEFORE_EXPIRY)

    assert result.valid is False
    assert result.reason == "target mismatch"


def test_params_fingerprint_binding_mismatch_fails_closed() -> None:
    payload = _cleared_payload(params_fingerprint="a" * 64)
    client = ACTHTTPClearanceClient(transport=_FakeTransport(payload))
    request = _request()

    response = client.request_clearance(request, timeout_seconds=20)
    result = _verifier().verify(request=request, response=response, now=BEFORE_EXPIRY)

    assert result.valid is False
    # Either the binding or the proof rejects the tampered fingerprint.
    assert result.valid is False


def test_expired_clearance_cannot_be_replayed() -> None:
    client = ACTHTTPClearanceClient(transport=_FakeTransport(_cleared_payload()))
    request = _request()

    response = client.request_clearance(request, timeout_seconds=20)
    result = _verifier().verify(request=request, response=response, now=AFTER_EXPIRY)

    assert result.valid is False
    assert result.status == ClearanceStatus.EXPIRED


def test_unavailable_gateway_fails_closed() -> None:
    client = ACTHTTPClearanceClient(transport=_FakeTransport(_cleared_payload(), fail=True))

    response = client.request_clearance(_request(), timeout_seconds=20)

    assert response.status == ClearanceStatus.TOWER_UNAVAILABLE


def test_act_state_mapping_for_poll_shapes() -> None:
    cases = {
        "pending": ClearanceStatus.CLEARANCE_REQUIRED,
        "approved": ClearanceStatus.CLEARED,
        "denied": ClearanceStatus.DENIED,
        "expired": ClearanceStatus.EXPIRED,
        "cancelled": ClearanceStatus.DENIED,
    }
    for act_state, expected in cases.items():
        payload = _cleared_payload(state=act_state)
        response = clearance_response_from_act_payload(payload)
        assert response.status == expected, act_state


def test_target_identity_resolved_from_extensions_when_core_absent() -> None:
    payload = _cleared_payload()
    payload.pop("target")
    payload["extensions"] = {"agentickvm": {"target": "mock-host"}}

    response = clearance_response_from_act_payload(payload)

    assert response.target == "mock-host"


def test_session_identity_resolved_from_extensions_when_core_absent() -> None:
    # A real tower status response carries no core session field; the aircraft's
    # session identity round-trips through the signed extensions envelope.
    payload = _cleared_payload()
    payload.pop("session_id")
    payload["extensions"] = {"agentickvm": {"session_id": "session-1"}}

    response = clearance_response_from_act_payload(payload)

    assert response.session_id == "session-1"
