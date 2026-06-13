import json
import stat
from datetime import UTC, datetime, timedelta

from agentickvm.control_plane import (
    ApprovalCacheError,
    ApprovalChannel,
    ApprovalGrantVerifier,
    GrantVerificationContext,
    HMACDevelopmentSigner,
    SignedApprovalCache,
    build_grant_payload,
)


NOW = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
PARAMS = {"force": True}


def _signed_grant():
    signer = HMACDevelopmentSigner(key_id="dev-key-1", secret=b"cache-test-secret")
    payload = build_grant_payload(
        grant_id="grant-1",
        request_id="approval-1",
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        parameters=PARAMS,
        risk_family="power",
        channel=ApprovalChannel.OUT_OF_BAND,
        expires_at=NOW + timedelta(minutes=5),
        signer_key_id=signer.key_id,
    )
    return signer.sign(payload), signer


def _context() -> GrantVerificationContext:
    return GrantVerificationContext.from_parameters(
        request_id="approval-1",
        session_id="session-1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        parameters=PARAMS,
        risk_family="power",
        now=NOW,
    )


def test_signed_cache_writes_explicit_path_with_0600_mode(tmp_path) -> None:
    grant, _ = _signed_grant()
    cache_path = tmp_path / "approvals.json"

    SignedApprovalCache(cache_path).write_signed_grants((grant,))

    assert cache_path.exists()
    assert stat.S_IMODE(cache_path.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "approvals.json.lock").stat().st_mode) == 0o600


def test_signed_cache_round_trips_signed_grants(tmp_path) -> None:
    grant, signer = _signed_grant()
    cache = SignedApprovalCache(tmp_path / "approvals.json")
    cache.write_signed_grants((grant,))

    loaded = cache.read_signed_grants()
    verified = cache.find_verified_grant(
        verifier=ApprovalGrantVerifier({signer.key_id: signer}),
        context=_context(),
    )

    assert len(loaded) == 1
    assert loaded[0].to_dict() == grant.to_dict()
    assert verified is not None


def test_cache_is_not_authority_for_unsigned_or_malformed_data(tmp_path) -> None:
    cache_path = tmp_path / "approvals.json"
    cache_path.write_text(
        json.dumps(
            {
                "version": 1,
                "authority": "cache_only_signature_required",
                "signed_grants": [{"payload": {"request_id": "approval-1"}}],
            }
        ),
        encoding="utf-8",
    )

    cache = SignedApprovalCache(cache_path)

    try:
        cache.read_signed_grants()
    except ApprovalCacheError:
        pass
    else:  # pragma: no cover - defensive assertion branch
        raise AssertionError("malformed unsigned cache unexpectedly loaded")
    assert cache.find_verified_grant(verifier=ApprovalGrantVerifier({}), context=_context()) is None


def test_manually_edited_cache_grant_fails_verification(tmp_path) -> None:
    grant, signer = _signed_grant()
    cache = SignedApprovalCache(tmp_path / "approvals.json")
    cache.write_signed_grants((grant,))
    payload = json.loads((tmp_path / "approvals.json").read_text(encoding="utf-8"))
    payload["signed_grants"][0]["payload"]["target"] = "other-target"
    (tmp_path / "approvals.json").write_text(json.dumps(payload), encoding="utf-8")

    result = cache.find_verified_grant(
        verifier=ApprovalGrantVerifier({signer.key_id: signer}),
        context=_context(),
    )

    assert result is None


def test_missing_cache_returns_no_grants(tmp_path) -> None:
    cache = SignedApprovalCache(tmp_path / "missing.json")

    assert cache.read_signed_grants() == ()
    assert cache.find_verified_grant(verifier=ApprovalGrantVerifier({}), context=_context()) is None
