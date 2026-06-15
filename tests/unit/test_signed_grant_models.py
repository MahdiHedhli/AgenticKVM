from datetime import UTC, datetime, timedelta

import pytest

from agentickvm.control_plane import (
    ApprovalChannel,
    ApprovalRiskSummary,
    ApprovalShortCode,
    FingerprintError,
    GrantPayload,
    GrantVerificationResult,
    GrantVerificationStatus,
    SignedApprovalGrant,
    canonical_json,
    fingerprint_broker_parameters,
)


NOW = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)


def _payload(**overrides: object) -> GrantPayload:
    values = {
        "grant_id": "grant-1",
        "request_id": "approval-1",
        "session_id": "session-1",
        "target": "mock-host",
        "provider": "mock",
        "capability": "power.force_restart",
        "params_fingerprint": "a" * 64,
        "risk_family": "power",
        "channel": ApprovalChannel.OUT_OF_BAND,
        "expires_at": NOW + timedelta(minutes=5),
        "one_time": True,
        "policy_constraints": {"mode": "Supervised"},
        "signer_key_id": "dev-key-1",
    }
    values.update(overrides)
    return GrantPayload(**values)


def test_parameter_fingerprint_is_stable_and_order_independent() -> None:
    first = fingerprint_broker_parameters({"b": [2, 1], "a": {"x": True}})
    second = fingerprint_broker_parameters({"a": {"x": True}, "b": [2, 1]})
    changed = fingerprint_broker_parameters({"a": {"x": False}, "b": [2, 1]})

    assert first == second
    assert first != changed
    assert len(first) == 64


def test_parameter_fingerprint_rejects_raw_bytes() -> None:
    with pytest.raises(FingerprintError, match="raw bytes"):
        fingerprint_broker_parameters({"screenshot": b"raw-image"})


def test_canonical_json_is_stable() -> None:
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'


def test_grant_payload_serializes_to_stable_json_safe_shape() -> None:
    payload = _payload()
    data = payload.to_dict()

    assert data["payload_version"] == "approval-grant-v1"
    assert data["request_id"] == "approval-1"
    assert data["channel"] == "out_of_band"
    assert data["consumed_at"] is None
    assert payload.canonical_payload() == canonical_json(data)


def test_grant_payload_requires_timezone_aware_expiry() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _payload(expires_at=datetime(2026, 6, 12, 12, 5))


def test_signed_approval_grant_serializes_without_raw_secrets() -> None:
    signed = SignedApprovalGrant(
        payload=_payload(),
        signature="deadbeef",
        signature_algorithm="hmac-sha256",
    )

    data = signed.to_dict()

    assert data["signature"] == "deadbeef"
    assert data["signature_algorithm"] == "hmac-sha256"
    assert "secret" not in canonical_json(data).lower()


def test_risk_summary_and_short_code_validation() -> None:
    summary = ApprovalRiskSummary(
        risk_family="power",
        summary="Restarting this target may disrupt availability.",
        material_risks=("availability disruption",),
    )
    short_code = ApprovalShortCode("ABCD-1234")

    assert summary.to_dict()["risk_family"] == "power"
    assert short_code.to_dict() == {"value": "ABCD-1234"}

    with pytest.raises(ValueError, match="short code"):
        ApprovalShortCode("")


def test_verification_result_is_json_safe() -> None:
    result = GrantVerificationResult(
        status=GrantVerificationStatus.REJECTED,
        reason="params fingerprint mismatch",
        request_id="approval-1",
        grant_id="grant-1",
        signer_key_id="dev-key-1",
    )

    assert result.valid is False
    assert result.to_dict()["status"] == "rejected"
