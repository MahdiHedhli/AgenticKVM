"""Production signer trust for the local_terminal approval channel.

The local_terminal auth channel clears through the local signed-grant broker.
For development that uses the symmetric ``HMACDevelopmentSigner`` (the agent can
read the key, so it is not a production authority). To make local_terminal
production-grade, this module adds:

* a keychain-backed signer that delegates signing to an injectable backend (a
  real macOS Keychain / OS key store for operators; a deterministic in-memory
  backend for tests and the explicit dev fallback), and
* a signer trust registry that grant verification consults so only trusted,
  non-development signers can authorize -- untrusted or development signers fail
  closed in production.

This is signing authority only. Risk tiering and the recommended mobile_signed
(ACT) path are unchanged.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Mapping, Protocol

from agentickvm.control_plane.approval_broker import ApprovalSigner
from agentickvm.control_plane.grants import GrantPayload, SignedApprovalGrant


class KeychainSignerBackend(Protocol):
    """Backend that holds signing material and signs/verifies opaque messages.

    A production backend keeps the private key in the OS keychain and never
    exposes it (asymmetric signing). The agent process cannot read the key.
    """

    def sign(self, *, key_id: str, message: bytes) -> str:
        """Return a signature for ``message`` under ``key_id``."""

    def verify(self, *, key_id: str, message: bytes, signature: str) -> bool:
        """Return whether ``signature`` verifies for ``message`` under ``key_id``."""


@dataclass(frozen=True)
class InMemoryKeychainBackend:
    """Deterministic in-memory backend for tests and the dev fallback only.

    NOT a production keychain: it uses a symmetric HMAC the holder can read. The
    real operator backend talks to the OS keychain with an asymmetric key.
    """

    keys: Mapping[str, bytes]

    def sign(self, *, key_id: str, message: bytes) -> str:
        secret = self.keys.get(key_id)
        if not secret:
            raise KeyError(f"no key material for {key_id!r}")
        return hmac.new(secret, message, sha256).hexdigest()

    def verify(self, *, key_id: str, message: bytes, signature: str) -> bool:
        secret = self.keys.get(key_id)
        if not secret:
            return False
        return hmac.compare_digest(
            hmac.new(secret, message, sha256).hexdigest(), signature
        )


@dataclass(frozen=True)
class KeychainApprovalSigner:
    """Approval signer whose key material lives behind a keychain backend."""

    key_id: str
    backend: KeychainSignerBackend
    signature_algorithm: str = "keychain"

    def __post_init__(self) -> None:
        if not self.key_id:
            raise ValueError("signer key id is required")

    def sign(self, payload: GrantPayload) -> SignedApprovalGrant:
        if payload.signer_key_id != self.key_id:
            raise ValueError("payload signer key id does not match signer")
        signature = self.backend.sign(
            key_id=self.key_id, message=payload.canonical_payload().encode("utf-8")
        )
        return SignedApprovalGrant(
            payload=payload,
            signature=signature,
            signature_algorithm=self.signature_algorithm,
        )

    def verify(self, signed_grant: SignedApprovalGrant) -> bool:
        if signed_grant.signature_algorithm != self.signature_algorithm:
            return False
        if signed_grant.payload.signer_key_id != self.key_id:
            return False
        return self.backend.verify(
            key_id=self.key_id,
            message=signed_grant.payload.canonical_payload().encode("utf-8"),
            signature=signed_grant.signature,
        )


@dataclass(frozen=True)
class SignerTrust:
    """A registered signer and whether it is a development (non-authority) key."""

    signer: ApprovalSigner
    development: bool
    label: str


class SignerTrustRegistry:
    """Trusted signer registry consulted by grant verification.

    Unknown signer key ids are untrusted (fail closed). Development signers are
    untrusted unless ``allow_development`` is explicitly set -- so the dev HMAC
    signer cannot authorize in a production configuration.
    """

    def __init__(self, *, allow_development: bool = False) -> None:
        self.allow_development = allow_development
        self._trust: dict[str, SignerTrust] = {}

    def register(
        self,
        signer: ApprovalSigner,
        *,
        development: bool = False,
        label: str | None = None,
    ) -> None:
        if not signer.key_id:
            raise ValueError("signer key id is required")
        self._trust[signer.key_id] = SignerTrust(
            signer=signer,
            development=development,
            label=label or ("development" if development else "production"),
        )

    def is_trusted(self, key_id: str) -> bool:
        trust = self._trust.get(key_id)
        if trust is None:
            return False
        if trust.development and not self.allow_development:
            return False
        return True

    def signer_for(self, key_id: str) -> ApprovalSigner | None:
        return self._trust[key_id].signer if self.is_trusted(key_id) else None

    def trusted_signers(self) -> dict[str, ApprovalSigner]:
        return {
            key_id: trust.signer
            for key_id, trust in self._trust.items()
            if self.is_trusted(key_id)
        }

    def trust_summary(self) -> list[dict[str, object]]:
        """Return an audit-friendly view of registered signers and trust state."""

        return [
            {
                "key_id": key_id,
                "signature_algorithm": trust.signer.signature_algorithm,
                "development": trust.development,
                "label": trust.label,
                "trusted": self.is_trusted(key_id),
            }
            for key_id, trust in sorted(self._trust.items())
        ]


__all__ = [
    "InMemoryKeychainBackend",
    "KeychainApprovalSigner",
    "KeychainSignerBackend",
    "SignerTrust",
    "SignerTrustRegistry",
]
