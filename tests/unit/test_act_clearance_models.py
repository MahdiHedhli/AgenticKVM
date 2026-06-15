from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from agentickvm.control_plane.act_client import (
    ACTClearanceVerifier,
    MockACTClient,
    MockACTProofVerifier,
    cleared_response_for,
)
from agentickvm.control_plane.clearance import (
    ClearanceOperatorMessage,
    ClearanceParamsFingerprint,
    ClearanceResponse,
    ClearanceRiskFamily,
    ClearanceShortCode,
    ClearanceStatus,
    build_clearance_request,
)


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _request(**params: object):
    return build_clearance_request(
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        parameters=params or {"reason": "wedged"},
        risk_family=ClearanceRiskFamily.HIGH_RISK,
        risk_summary="forced restart",
        material_risks=("availability disruption",),
        intended_effect="recover wedged machine",
        requested_by="agent",
        audit_correlation_id="corr-1",
        policy_context={"decision": "ask_each_time"},
        now=NOW,
        request_id="request-1",
    )


def test_clearance_request_serializes_with_short_code_and_operator_message() -> None:
    request = _request()

    payload = request.to_dict()

    assert payload["aircraft"] == "AgenticKVM"
    assert payload["request_id"] == "request-1"
    assert payload["risk_family"] == "high_risk"
    assert payload["short_code"]
    assert "Clearance" in payload["operator_message"]
    assert "Surface this code to the operator" in payload["operator_message"]
    assert ".." not in payload["operator_message"]
    assert isinstance(request.operator_message, ClearanceOperatorMessage)
    assert isinstance(request.params_fingerprint, ClearanceParamsFingerprint)
    assert isinstance(request.short_code, ClearanceShortCode)


def test_clearance_fingerprint_is_stable_and_changes_with_params() -> None:
    first = _request(a=1, b=2)
    second = _request(b=2, a=1)
    changed = _request(a=1, b=3)

    assert first.params_fingerprint == second.params_fingerprint
    assert first.params_fingerprint != changed.params_fingerprint


def test_mock_act_client_returns_expected_statuses() -> None:
    request = _request()

    pending = MockACTClient().request_clearance(request, timeout_seconds=20)
    cleared = MockACTClient(default_status=ClearanceStatus.CLEARED).request_clearance(
        request,
        timeout_seconds=20,
    )
    denied = MockACTClient().deny_clearance("request-1", reason="operator denied", timeout_seconds=20)

    assert pending.status == ClearanceStatus.CLEARANCE_REQUIRED
    assert cleared.status == ClearanceStatus.CLEARED
    assert denied.status == ClearanceStatus.DENIED
    assert pending.risk_family == ClearanceRiskFamily.HIGH_RISK
    assert pending.expires_at == request.expires_at
    assert isinstance(pending.short_code, ClearanceShortCode)


def test_matching_mock_clearance_verifies_in_test_mode() -> None:
    request = _request()
    response = cleared_response_for(request)
    verifier = ACTClearanceVerifier(
        tower_id="mock-act",
        proof_verifier=MockACTProofVerifier(),
        test_mode=True,
    )

    result = verifier.verify(request=request, response=response, now=NOW)

    assert result.valid is True
    assert result.status == ClearanceStatus.CLEARED


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("target", "other-target", "target mismatch"),
        ("provider", "other-provider", "provider mismatch"),
        ("capability", "observe.status", "capability mismatch"),
        ("params_fingerprint", "wrong", "params_fingerprint mismatch"),
        ("risk_family", ClearanceRiskFamily.LOW_RISK, "risk_family mismatch"),
        ("short_code", "DIFF-0000", "short_code mismatch"),
    ],
)
def test_mismatched_mock_clearance_fails_closed(
    field: str,
    value: str | ClearanceRiskFamily,
    reason: str,
) -> None:
    request = _request()
    response = cleared_response_for(request)
    response = replace(response, **{field: value})
    verifier = ACTClearanceVerifier(
        tower_id="mock-act",
        proof_verifier=MockACTProofVerifier(),
        test_mode=True,
    )

    result = verifier.verify(request=request, response=response, now=NOW)

    assert result.valid is False
    assert result.reason == reason


def test_missing_proof_fails_closed_outside_mock_mode() -> None:
    request = _request()
    response = ClearanceResponse(
        status=ClearanceStatus.CLEARED,
        request_id=request.request_id,
        session_id=request.session_id,
        target=request.target,
        provider=request.provider,
        capability=request.capability,
        params_fingerprint=request.params_fingerprint,
        risk_family=request.risk_summary.risk_family,
        short_code=request.short_code,
        expires_at=request.expires_at,
        tower_id="act",
        proof=None,
        audit_correlation_id=request.audit_correlation_id,
    )
    verifier = ACTClearanceVerifier(tower_id="act")

    result = verifier.verify(request=request, response=response, now=NOW)

    assert result.valid is False
    assert result.reason == "ACT clearance proof is required"


def test_expired_clearance_fails_closed() -> None:
    request = _request()
    response = ClearanceResponse(
        status=ClearanceStatus.CLEARED,
        request_id=request.request_id,
        session_id=request.session_id,
        target=request.target,
        provider=request.provider,
        capability=request.capability,
        params_fingerprint=request.params_fingerprint,
        risk_family=request.risk_summary.risk_family,
        short_code=request.short_code,
        expires_at=NOW - timedelta(seconds=1),
        tower_id="mock-act",
        proof={"mock_act_proof": "verified"},
        audit_correlation_id=request.audit_correlation_id,
    )
    verifier = ACTClearanceVerifier(
        tower_id="mock-act",
        proof_verifier=MockACTProofVerifier(),
        test_mode=True,
    )

    result = verifier.verify(request=request, response=response, now=NOW)

    assert result.valid is False
    assert result.status == ClearanceStatus.EXPIRED
