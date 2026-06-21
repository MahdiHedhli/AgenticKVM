"""Production signer trust for the local_terminal channel.

A keychain-backed signer signs approval grants behind an injectable backend, and
a signer trust registry ensures only trusted, non-development signers can
authorize. The development HMAC signer is untrusted in a production registry, so
a grant signed by it fails closed. Mock-only: the keychain backend here is an
in-memory deterministic stand-in for the OS keychain.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agentickvm.control_plane import (
    ApprovalChannel,
    ApprovalGrantVerifier,
    GrantVerificationContext,
    GrantVerificationStatus,
    HMACDevelopmentSigner,
    InMemoryKeychainBackend,
    KeychainApprovalSigner,
    SignerTrustRegistry,
    build_grant_payload,
)

NOW = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)
PARAMS = {"reason": "recover wedged fixture", "force": True}


def _keychain_signer(key_id: str = "keychain-key-1") -> KeychainApprovalSigner:
    backend = InMemoryKeychainBackend(keys={key_id: b"operator-keychain-material"})
    return KeychainApprovalSigner(key_id=key_id, backend=backend)


def _dev_signer(key_id: str = "dev-key-1") -> HMACDevelopmentSigner:
    return HMACDevelopmentSigner(key_id=key_id, secret=b"agent-readable-dev-secret")


def _context(**overrides) -> GrantVerificationContext:
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


def _grant(signer, **overrides):
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


def test_keychain_signer_round_trips() -> None:
    signer = _keychain_signer()
    grant = _grant(signer)

    assert signer.verify(grant) is True


def test_keychain_signer_rejects_tampered_signature() -> None:
    signer = _keychain_signer()
    grant = _grant(signer)
    tampered = grant.__class__(
        payload=grant.payload,
        signature="deadbeef",
        signature_algorithm=grant.signature_algorithm,
    )

    assert signer.verify(tampered) is False


def test_keychain_signer_unknown_key_material_fails_closed() -> None:
    # A grant validly signed when key material is present must fail closed when
    # the verifying signer's backend no longer holds that key.
    present = KeychainApprovalSigner(
        key_id="rotated-key", backend=InMemoryKeychainBackend(keys={"rotated-key": b"material"})
    )
    grant = _grant(present)
    absent = KeychainApprovalSigner(
        key_id="rotated-key", backend=InMemoryKeychainBackend(keys={})
    )

    assert present.verify(grant) is True
    assert absent.verify(grant) is False


def test_registry_trusts_production_signer_not_development() -> None:
    registry = SignerTrustRegistry(allow_development=False)
    keychain = _keychain_signer()
    dev = _dev_signer()
    registry.register(keychain, development=False, label="keychain")
    registry.register(dev, development=True, label="hmac-dev")

    assert registry.is_trusted("keychain-key-1") is True
    assert registry.is_trusted("dev-key-1") is False
    assert registry.is_trusted("never-registered") is False
    assert set(registry.trusted_signers()) == {"keychain-key-1"}


def test_registry_can_explicitly_allow_development_signers() -> None:
    registry = SignerTrustRegistry(allow_development=True)
    registry.register(_dev_signer(), development=True)

    assert registry.is_trusted("dev-key-1") is True


def test_grant_verifier_from_registry_accepts_trusted_keychain_grant() -> None:
    keychain = _keychain_signer()
    registry = SignerTrustRegistry(allow_development=False)
    registry.register(keychain, development=False)
    verifier = ApprovalGrantVerifier.from_trust_registry(registry)

    result = verifier.verify(_grant(keychain), context=_context())

    assert result.valid is True
    assert result.status == GrantVerificationStatus.VALID


def test_grant_verifier_from_registry_rejects_development_signer_grant() -> None:
    dev = _dev_signer()
    registry = SignerTrustRegistry(allow_development=False)
    registry.register(_keychain_signer(), development=False)
    registry.register(dev, development=True)
    verifier = ApprovalGrantVerifier.from_trust_registry(registry)

    result = verifier.verify(_grant(dev), context=_context())

    assert result.valid is False
    assert result.reason == "untrusted signer key id"


def test_trust_summary_is_audit_friendly() -> None:
    registry = SignerTrustRegistry(allow_development=False)
    registry.register(_keychain_signer(), development=False, label="keychain")
    registry.register(_dev_signer(), development=True, label="hmac-dev")

    summary = registry.trust_summary()

    by_key = {row["key_id"]: row for row in summary}
    assert by_key["keychain-key-1"]["trusted"] is True
    assert by_key["keychain-key-1"]["development"] is False
    assert by_key["dev-key-1"]["trusted"] is False
    assert by_key["dev-key-1"]["development"] is True
