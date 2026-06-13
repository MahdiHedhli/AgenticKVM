"""Signed approval cache storage.

The cache persists signed approval grants for operator workflows. It is not an
authority boundary. Callers must verify signatures and exact request bindings
before using any cached grant.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import fcntl

from agentickvm.control_plane.approval_broker import (
    ApprovalGrantVerifier,
    GrantVerificationContext,
)
from agentickvm.control_plane.grants import SignedApprovalGrant


class ApprovalCacheError(RuntimeError):
    """Raised when signed approval cache storage is invalid."""


class SignedApprovalCache:
    """Explicit-path signed approval cache."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.exists() and self.path.is_dir():
            raise ApprovalCacheError("approval cache path must be a file")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def write_signed_grants(self, grants: tuple[SignedApprovalGrant, ...]) -> None:
        """Atomically write signed grants with `0600` permissions."""

        payload = {
            "version": 1,
            "authority": "cache_only_signature_required",
            "signed_grants": [grant.to_dict() for grant in grants],
        }
        encoded = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
        with self._locked():
            self._atomic_write(encoded)

    def append_signed_grant(self, grant: SignedApprovalGrant) -> None:
        """Append a signed grant by rewriting the cache atomically."""

        existing = self.read_signed_grants() if self.path.exists() else ()
        self.write_signed_grants((*existing, grant))

    def read_signed_grants(self) -> tuple[SignedApprovalGrant, ...]:
        """Read signed grants from cache.

        This method validates cache shape only. It does not grant authority.
        """

        if not self.path.exists():
            return ()
        with self._locked():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as exc:  # pragma: no cover - exact JSON error varies
                raise ApprovalCacheError("approval cache is malformed") from exc
        if not isinstance(payload, dict):
            raise ApprovalCacheError("approval cache root must be an object")
        if payload.get("authority") != "cache_only_signature_required":
            raise ApprovalCacheError("approval cache authority marker is invalid")
        grants = payload.get("signed_grants")
        if not isinstance(grants, list):
            raise ApprovalCacheError("approval cache signed_grants must be a list")
        try:
            return tuple(SignedApprovalGrant.from_dict(item) for item in grants)
        except Exception as exc:
            raise ApprovalCacheError("approval cache contains invalid signed grant") from exc

    def find_verified_grant(
        self,
        *,
        verifier: ApprovalGrantVerifier,
        context: GrantVerificationContext,
    ) -> SignedApprovalGrant | None:
        """Return the first cached grant that verifies for the context."""

        try:
            grants = self.read_signed_grants()
        except ApprovalCacheError:
            return None
        for grant in grants:
            if verifier.verify(grant, context=context).valid:
                return grant
        return None

    def _atomic_write(self, text: str) -> None:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
            text=True,
        )
        temp_path = Path(temp_name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            os.chmod(self.path, 0o600)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @contextmanager
    def _locked(self) -> Iterator[None]:
        fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "r+") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            pass
