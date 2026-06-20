"""Real ACT clearance proof verification (``ACT-CLEARANCE-PROOF-V1``).

ACT signs each cleared clearance with an Ed25519 proof over a fixed canonical
string (see the Tower's ``contracts/clearance/proof-format.md``). This module is
the AgenticKVM client-side verifier for that proof. It replaces the fail-closed
``ACTPendingProofVerifier`` now that ACT has published the canonical proof
format, schema (``act.clearance.v2``), and a committed verification vector.

The Ed25519 verification is a vendored pure-Python RFC 8032 implementation so the
client carries no third-party crypto dependency and verifies fully offline. Proof
verification operates on public data (a tower public key and a signature), so a
constant-time implementation is not required. Verification fails closed on any
missing field, unknown tower key, unsupported contract version, or bad signature.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Mapping

ACT_PROOF_ALGORITHM = "Ed25519"
ACT_PROOF_CANONICALIZATION = "ACT-CLEARANCE-PROOF-V1"

# Exact signed field order from the Tower proof-format contract.
ACT_PROOF_FIELD_ORDER: tuple[str, ...] = (
    "approval_id",
    "params_fingerprint",
    "short_code",
    "risk_family",
    "expires_at",
    "tower_id",
    "contract_version",
    "extensions_digest",
)

SUPPORTED_CONTRACT_VERSIONS = frozenset({"act.clearance.v1", "act.clearance.v2"})


class ACTProofError(ValueError):
    """Raised for malformed tower keys; verification itself fails closed."""


# --------------------------------------------------------------------------- #
# Vendored RFC 8032 Ed25519 verification (public-data signature check only).
# --------------------------------------------------------------------------- #

_P = 2**255 - 19
_D = (-121665 * pow(121666, _P - 2, _P)) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _inv(x: int) -> int:
    return pow(x, _P - 2, _P)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = (x * _I) % _P
    if x % 2 != 0:
        x = _P - x
    return x


_BY = (4 * _inv(5)) % _P
_BX = _xrecover(_BY)
_B = (_BX % _P, _BY % _P)


def _edwards_add(p_point: tuple[int, int], q_point: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = p_point
    x2, y2 = q_point
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _D * x1 * x2 * y1 * y2) % _P
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _D * x1 * x2 * y1 * y2) % _P
    return (x3 % _P, y3 % _P)


def _scalarmult(point: tuple[int, int], scalar: int) -> tuple[int, int]:
    if scalar == 0:
        return (0, 1)
    half = _scalarmult(point, scalar // 2)
    doubled = _edwards_add(half, half)
    if scalar & 1:
        doubled = _edwards_add(doubled, point)
    return doubled


def _decode_point(data: bytes) -> tuple[int, int]:
    raw = int.from_bytes(data, "little")
    y = raw & ((1 << 255) - 1)
    x = _xrecover(y)
    if (x & 1) != ((raw >> 255) & 1):
        x = _P - x
    point = (x, y)
    if (-x * x + y * y - 1 - _D * x * x * y * y) % _P != 0:
        raise ValueError("point is not on the Ed25519 curve")
    return point


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Return whether ``signature`` is a valid Ed25519 signature of ``message``."""

    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        sig_r = _decode_point(signature[:32])
        pub_a = _decode_point(public_key)
        sig_s = int.from_bytes(signature[32:], "little")
        digest = int.from_bytes(
            hashlib.sha512(signature[:32] + public_key + message).digest(), "little"
        )
        left = _scalarmult(_B, sig_s)
        right = _edwards_add(sig_r, _scalarmult(pub_a, digest))
        return left == right
    except (ValueError, OverflowError):
        return False


def decode_b64url(value: str) -> bytes:
    """Decode unpadded base64url as ACT emits tower keys and signatures."""

    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


# --------------------------------------------------------------------------- #
# Tower key registry + proof verifier
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TowerKeyRegistry:
    """Map ACT proof ``key_id`` values to 32-byte Ed25519 public keys."""

    keys: Mapping[str, bytes]

    @classmethod
    def from_b64url(cls, keys: Mapping[str, str]) -> "TowerKeyRegistry":
        """Build a registry from base64url-encoded tower public keys."""

        decoded: dict[str, bytes] = {}
        for key_id, encoded in keys.items():
            raw = decode_b64url(encoded)
            if len(raw) != 32:
                raise ACTProofError(f"tower key {key_id!r} is not 32 bytes")
            decoded[key_id] = raw
        return cls(keys=decoded)

    def public_key_for(self, key_id: str) -> bytes | None:
        return self.keys.get(key_id)


def build_clearance_proof_message(material: Mapping[str, str]) -> bytes:
    """Build the exact UTF-8 canonical ACT-CLEARANCE-PROOF-V1 string."""

    lines = [ACT_PROOF_CANONICALIZATION]
    for field_name in ACT_PROOF_FIELD_ORDER:
        if field_name not in material:
            raise ACTProofError(f"proof material missing field: {field_name}")
        lines.append(str(material[field_name]))
    return "\n".join(lines).encode("utf-8")


def verify_clearance_proof(
    *,
    material: Mapping[str, str],
    proof: Mapping[str, object],
    registry: TowerKeyRegistry,
) -> bool:
    """Verify an ACT clearance proof over its bound material. Fails closed."""

    try:
        if proof.get("algorithm") != ACT_PROOF_ALGORITHM:
            return False
        if proof.get("canonicalization") != ACT_PROOF_CANONICALIZATION:
            return False
        if material.get("contract_version") not in SUPPORTED_CONTRACT_VERSIONS:
            return False
        fields = proof.get("fields")
        if fields is not None and tuple(fields) != ACT_PROOF_FIELD_ORDER:
            return False
        # The proof's extensions_digest must match the bound material digest.
        proof_digest = proof.get("extensions_digest")
        if proof_digest is not None and proof_digest != material.get("extensions_digest"):
            return False
        key_id = proof.get("key_id")
        signature = proof.get("signature")
        if not isinstance(key_id, str) or not isinstance(signature, str):
            return False
        public_key = registry.public_key_for(key_id)
        if public_key is None:
            return False
        message = build_clearance_proof_message(material)
        return ed25519_verify(public_key, message, decode_b64url(signature))
    except (ACTProofError, ValueError, TypeError):
        return False


@dataclass(frozen=True)
class ACTClearanceProofVerifier:
    """Production ClearanceProofVerifier backed by real Ed25519 verification.

    This is the real replacement for ``ACTPendingProofVerifier``. It verifies the
    Ed25519 proof a cleared ACT response carries against the bound material the
    response preserved verbatim from the wire (``ClearanceResponse.bound_material``).
    """

    registry: TowerKeyRegistry

    def verify_proof(self, *, request, response) -> bool:
        proof = getattr(response, "proof", None)
        material = getattr(response, "bound_material", None)
        if not proof or not material:
            return False
        return verify_clearance_proof(material=material, proof=proof, registry=self.registry)


__all__ = [
    "ACT_PROOF_ALGORITHM",
    "ACT_PROOF_CANONICALIZATION",
    "ACT_PROOF_FIELD_ORDER",
    "ACTClearanceProofVerifier",
    "ACTProofError",
    "SUPPORTED_CONTRACT_VERSIONS",
    "TowerKeyRegistry",
    "build_clearance_proof_message",
    "decode_b64url",
    "ed25519_verify",
    "verify_clearance_proof",
]
