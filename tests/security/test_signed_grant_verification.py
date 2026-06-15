from datetime import UTC, datetime, timedelta

from agentickvm.control_plane import (
    ApprovalChannel,
    ApprovalGrantVerifier,
    GrantVerificationContext,
    GrantVerificationStatus,
    HMACDevelopmentSigner,
    SignedApprovalGrant,
    build_grant_payload,
)


NOW = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
PARAMS = {"reason": "recover wedged fixture", "force": True}


def _signer(secret: bytes = b"test-only-dev-secret") -> HMACDevelopmentSigner:
    return HMACDevelopmentSigner(key_id="dev-key-1", secret=secret)


def _context(**overrides: object) -> GrantVerificationContext:
    values = {
        "request_id": "approval-1",
        "session_id": "session-1",
        "target": "mock-host",
        "provider": "mock",
        "capability": "power.force_restart",
        "parameters": PARAMS,
        "risk_family": "power",
        "now": NOW,
    }
    values.update(overrides)
    return GrantVerificationContext.from_parameters(**values)


def _signed_grant(**overrides: object) -> SignedApprovalGrant:
    signer = _signer()
    values = {
        "grant_id": "grant-1",
        "request_id": "approval-1",
        "session_id": "session-1",
        "target": "mock-host",
        "provider": "mock",
        "capability": "power.force_restart",
        "parameters": PARAMS,
        "risk_family": "power",
        "channel": ApprovalChannel.OUT_OF_BAND,
        "expires_at": NOW + timedelta(minutes=5),
        "signer_key_id": signer.key_id,
    }
    values.update(overrides)
    return signer.sign(build_grant_payload(**values))


def _verifier(signer: HMACDevelopmentSigner | None = None) -> ApprovalGrantVerifier:
    signer = signer or _signer()
    return ApprovalGrantVerifier({signer.key_id: signer})


def test_valid_signed_grant_verifies() -> None:
    result = _verifier().verify(_signed_grant(), context=_context())

    assert result.valid is True
    assert result.status == GrantVerificationStatus.VALID
    assert result.reason == "grant verified"


def test_unsigned_grant_fails_closed() -> None:
    result = _verifier().verify(None, context=_context())

    assert result.status == GrantVerificationStatus.UNSIGNED


def test_tampered_payload_fails_signature_verification() -> None:
    signed = _signed_grant()
    tampered = SignedApprovalGrant(
        payload=signed.payload.with_consumed_at(NOW),
        signature=signed.signature,
        signature_algorithm=signed.signature_algorithm,
    )

    result = _verifier().verify(tampered, context=_context())

    assert result.status == GrantVerificationStatus.REJECTED
    assert result.reason == "invalid signature"


def test_wrong_key_fails_verification() -> None:
    signed = _signed_grant()
    wrong_signer = HMACDevelopmentSigner(key_id="dev-key-1", secret=b"wrong-secret")

    result = _verifier(wrong_signer).verify(signed, context=_context())

    assert result.status == GrantVerificationStatus.REJECTED
    assert result.reason == "invalid signature"


def test_untrusted_key_id_fails_verification() -> None:
    result = ApprovalGrantVerifier({}).verify(_signed_grant(), context=_context())

    assert result.status == GrantVerificationStatus.REJECTED
    assert result.reason == "untrusted signer key id"


def test_parameter_mismatch_fails_closed() -> None:
    result = _verifier().verify(
        _signed_grant(),
        context=_context(parameters={"reason": "different", "force": True}),
    )

    assert result.status == GrantVerificationStatus.REJECTED
    assert result.reason == "params_fingerprint mismatch"


def test_target_provider_capability_and_risk_mismatches_fail_closed() -> None:
    for field, value, reason in (
        ("target", "other-target", "target mismatch"),
        ("provider", "other-provider", "provider mismatch"),
        ("capability", "observe.status", "capability mismatch"),
        ("risk_family", "observe", "risk_family mismatch"),
    ):
        result = _verifier().verify(_signed_grant(), context=_context(**{field: value}))
        assert result.status == GrantVerificationStatus.REJECTED
        assert result.reason == reason


def test_expired_and_consumed_grants_fail_closed() -> None:
    expired = _signed_grant(expires_at=NOW - timedelta(seconds=1))
    consumed_payload = build_grant_payload(
        grant_id="grant-2",
        request_id="approval-1",
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        parameters=PARAMS,
        risk_family="power",
        channel=ApprovalChannel.OUT_OF_BAND,
        expires_at=NOW + timedelta(minutes=5),
        signer_key_id=_signer().key_id,
    ).with_consumed_at(NOW)
    consumed = _signer().sign(consumed_payload)

    assert _verifier().verify(expired, context=_context()).status == GrantVerificationStatus.EXPIRED
    assert _verifier().verify(consumed, context=_context()).status == GrantVerificationStatus.CONSUMED


def test_hard_invariant_capability_cannot_be_approved() -> None:
    signed = _signed_grant(
        capability="session.disable_audit",
        risk_family="audit",
    )
    result = _verifier().verify(
        signed,
        context=_context(
            capability="session.disable_audit",
            risk_family="audit",
        ),
    )

    assert result.status == GrantVerificationStatus.REJECTED
    assert result.reason == "hard invariant capability cannot be approved"


def test_conversational_approval_is_banned_for_power() -> None:
    signed = _signed_grant(channel=ApprovalChannel.CONVERSATIONAL)

    result = _verifier().verify(signed, context=_context())

    assert result.status == GrantVerificationStatus.REJECTED
    assert result.reason == "conversational approval banned for risk family"


def test_conversational_approval_can_verify_for_flagged_low_risk_observe() -> None:
    params = {"detail": "summary"}
    signed = _signed_grant(
        capability="observe.status",
        parameters=params,
        risk_family="observe",
        channel=ApprovalChannel.CONVERSATIONAL,
    )

    result = _verifier().verify(
        signed,
        context=_context(
            capability="observe.status",
            parameters=params,
            risk_family="observe",
        ),
    )

    assert result.status == GrantVerificationStatus.VALID
