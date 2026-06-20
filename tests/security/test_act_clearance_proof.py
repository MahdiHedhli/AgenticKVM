"""Real ACT clearance proof verification against the committed tower vector.

The material/proof/public key below are copied verbatim from the Agentic Control
Tower published contract vector (``contracts/clearance/test-vector.json`` +
``proof-format.md``). Verifying it proves the AgenticKVM client speaks the real
``ACT-CLEARANCE-PROOF-V1`` proof format end-to-end, with no network and no
third-party crypto dependency. Tampering or an unknown tower key must fail closed.
"""

from __future__ import annotations

from types import SimpleNamespace

from agentickvm.control_plane import (
    ACT_PROOF_CANONICALIZATION,
    ACTClearanceProofVerifier,
    TowerKeyRegistry,
    build_clearance_proof_message,
    verify_clearance_proof,
)

TOWER_PUBLIC_KEY_B64URL = "OGpHYc-bD8rOc-IQfh8jWn6nO1gc3qpEvm8EbHXXWAc"

VECTOR_MATERIAL = {
    "approval_id": "appr_test_vector",
    "params_fingerprint": "f" * 64,
    "short_code": "ABC123DEF0",
    "risk_family": "external_effect",
    "expires_at": "2026-06-18T12:00:00Z",
    "tower_id": "tower_test",
    "contract_version": "act.clearance.v1",
    "extensions_digest": "0" * 64,
}

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


def _registry(key_id: str = "tower:tower_test") -> TowerKeyRegistry:
    return TowerKeyRegistry.from_b64url({key_id: TOWER_PUBLIC_KEY_B64URL})


def test_canonical_proof_message_matches_contract_format() -> None:
    message = build_clearance_proof_message(VECTOR_MATERIAL)

    assert message.decode("utf-8").splitlines() == [
        ACT_PROOF_CANONICALIZATION,
        "appr_test_vector",
        "f" * 64,
        "ABC123DEF0",
        "external_effect",
        "2026-06-18T12:00:00Z",
        "tower_test",
        "act.clearance.v1",
        "0" * 64,
    ]


def test_committed_tower_vector_verifies() -> None:
    assert (
        verify_clearance_proof(
            material=VECTOR_MATERIAL, proof=VECTOR_PROOF, registry=_registry()
        )
        is True
    )


def test_proof_verifier_verifies_committed_vector_on_a_response() -> None:
    response = SimpleNamespace(proof=VECTOR_PROOF, bound_material=VECTOR_MATERIAL)
    verifier = ACTClearanceProofVerifier(registry=_registry())

    assert verifier.verify_proof(request=None, response=response) is True


def test_every_bound_field_is_tamper_evident() -> None:
    registry = _registry()
    for field_name in VECTOR_MATERIAL:
        tampered = dict(VECTOR_MATERIAL)
        tampered[field_name] = (
            tampered[field_name] + "x"
            if field_name not in {"params_fingerprint", "extensions_digest"}
            else "e" * 64
        )
        assert (
            verify_clearance_proof(material=tampered, proof=VECTOR_PROOF, registry=registry)
            is False
        ), field_name


def test_unknown_tower_key_fails_closed() -> None:
    registry = TowerKeyRegistry.from_b64url({"tower:other": TOWER_PUBLIC_KEY_B64URL})

    assert (
        verify_clearance_proof(material=VECTOR_MATERIAL, proof=VECTOR_PROOF, registry=registry)
        is False
    )


def test_wrong_algorithm_or_canonicalization_fails_closed() -> None:
    registry = _registry()
    bad_alg = {**VECTOR_PROOF, "algorithm": "RSA"}
    bad_canon = {**VECTOR_PROOF, "canonicalization": "OTHER"}

    assert verify_clearance_proof(material=VECTOR_MATERIAL, proof=bad_alg, registry=registry) is False
    assert verify_clearance_proof(material=VECTOR_MATERIAL, proof=bad_canon, registry=registry) is False


def test_unsupported_contract_version_fails_closed() -> None:
    material = {**VECTOR_MATERIAL, "contract_version": "act.clearance.v9"}

    assert verify_clearance_proof(material=material, proof=VECTOR_PROOF, registry=_registry()) is False


def test_mismatched_extensions_digest_fails_closed() -> None:
    # proof.extensions_digest must agree with the bound material digest.
    material = {**VECTOR_MATERIAL, "extensions_digest": "1" * 64}

    assert verify_clearance_proof(material=material, proof=VECTOR_PROOF, registry=_registry()) is False


def test_verifier_fails_closed_without_proof_or_material() -> None:
    verifier = ACTClearanceProofVerifier(registry=_registry())

    assert verifier.verify_proof(request=None, response=SimpleNamespace(proof=None, bound_material=VECTOR_MATERIAL)) is False
    assert verifier.verify_proof(request=None, response=SimpleNamespace(proof=VECTOR_PROOF, bound_material=None)) is False
