"""Shared pinned, clearance-gated HTTPS JSON client for live MUTATION paths.

This module contains real network primitives (``ssl`` + ``http.client``) and
therefore lives outside the provider package, next to the GET-only read
client. Provider modules must never import it; automated tests exercise it
only through injected fake connection factories.

Safety posture (stricter than the read client):

- Only POST and PATCH exist on this surface; every other method — including
  GET — fails closed before a connection is opened. Mutation is a separate
  explicit path, never a superset of the read path.
- A pinned SHA-256 certificate fingerprint is REQUIRED. There is no
  verified-chain fallback for mutation: no pin, no client. The pin is checked
  after the handshake and before any request bytes (credentials) are sent.
- Construction requires a genuine ``VerifiedMutationClearance`` handle, so
  credential headers can only exist downstream of a verified Ed25519
  clearance proof. Expiry is re-checked before every request.
- Credential material never appears in errors, logs, or ``repr``.
"""

from __future__ import annotations

import json
import ssl
from collections.abc import Mapping
from datetime import UTC, datetime
from http.client import HTTPSConnection
from typing import Any, Callable

from agentickvm.live_validation.http_read import (
    HTTPSConnectionFactory,
    default_https_connection_factory,
)
from agentickvm.providers.errors import (
    ProviderAuthenticationFailedError,
    ProviderConnectionError,
    ProviderMutationBlockedError,
    ProviderProtocolError,
    ProviderResponseValidationError,
    ProviderTLSVerificationError,
)
from agentickvm.providers.mutation_gate import VerifiedMutationClearance
from agentickvm.providers.pikvm_transport import (
    normalize_cert_fingerprint,
    sha256_fingerprint_for_der,
)
from agentickvm.providers.transport_policy import TransportSecurityPolicy

_ALLOWED_MUTATING_METHODS = frozenset({"POST", "PATCH"})


class PinnedMutatingHTTPSJSONClient:
    """HTTPS JSON client that can only issue clearance-gated POST/PATCH."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        headers: Mapping[str, str],
        pinned_sha256: str | None,
        clearance: object,
        policy: TransportSecurityPolicy | None = None,
        connection_factory: HTTPSConnectionFactory | None = None,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        if not pinned_sha256:
            raise ProviderMutationBlockedError(
                "mutating HTTPS client requires a pinned certificate "
                "fingerprint; no pin means no mutation"
            )
        if not isinstance(clearance, VerifiedMutationClearance):
            raise ProviderMutationBlockedError(
                "mutating HTTPS client requires a verified mutation clearance handle"
            )
        self._host = host
        self._port = port
        self._headers = dict(headers)
        self._pinned_sha256 = normalize_cert_fingerprint(pinned_sha256)
        self._clearance = clearance
        self.policy = policy or TransportSecurityPolicy()
        self._connection_factory = connection_factory or default_https_connection_factory
        self._now_factory = now_factory or (lambda: datetime.now(UTC))

    def __repr__(self) -> str:  # pragma: no cover - shape guard only
        return (
            f"<{type(self).__name__} host=[REDACTED] pinned=True "
            f"capability={self._clearance.capability}>"
        )

    def post_json(
        self, path: str, body: Mapping[str, Any], *, timeout_seconds: float
    ) -> Mapping[str, Any]:
        """Perform a clearance-gated mutating POST."""

        return self.request_json("POST", path, body, timeout_seconds=timeout_seconds)

    def patch_json(
        self, path: str, body: Mapping[str, Any], *, timeout_seconds: float
    ) -> Mapping[str, Any]:
        """Perform a clearance-gated mutating PATCH."""

        return self.request_json("PATCH", path, body, timeout_seconds=timeout_seconds)

    def request_json(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        """Fail closed for every method except POST/PATCH, then mutate."""

        if method.upper() not in _ALLOWED_MUTATING_METHODS:
            raise ProviderMutationBlockedError(
                "live mutation client refuses non-mutating methods; use the "
                "read layer for reads"
            )
        if not path.startswith("/"):
            raise ProviderProtocolError("live mutation client requires absolute paths")
        if self._now_factory().astimezone(UTC) >= self._clearance.expires_at.astimezone(UTC):
            raise ProviderMutationBlockedError(
                "mutation clearance expired; request refused before connecting"
            )
        encoded = json.dumps(dict(body)).encode("utf-8")
        headers = dict(self._headers)
        headers["Content-Type"] = "application/json"
        connection = self._connection_factory(
            self._host,
            self._port,
            self._build_ssl_context(),
            timeout_seconds,
        )
        try:
            try:
                connection.connect()
                self._enforce_pin(connection)
                connection.request(method.upper(), path, body=encoded, headers=headers)
                response = connection.getresponse()
                status = int(response.status)
                response_body = response.read(self.policy.max_response_bytes + 1)
                content_type = str(response.getheader("Content-Type") or "")
            except (
                ProviderTLSVerificationError,
                ProviderProtocolError,
                ProviderMutationBlockedError,
            ):
                raise
            except (OSError, ssl.SSLError) as exc:
                raise ProviderConnectionError(
                    f"live mutation connection failed for {method.upper()} {path}"
                ) from exc
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001 - close must never mask the real error
                pass
        if status in (401, 403):
            raise ProviderAuthenticationFailedError(
                f"live mutation authentication failed with status {status} "
                f"for {method.upper()} {path}"
            )
        if status >= 300:
            raise ProviderProtocolError(
                f"live mutation request failed with status {status} "
                f"for {method.upper()} {path}"
            )
        if len(response_body) > self.policy.max_response_bytes:
            raise ProviderResponseValidationError(
                f"live mutation response exceeded {self.policy.max_response_bytes} bytes"
            )
        if not response_body:
            return {}
        if content_type and "json" not in content_type.lower():
            raise ProviderResponseValidationError(
                f"live mutation response for {method.upper()} {path} is not JSON"
            )
        try:
            payload = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ProviderResponseValidationError(
                f"live mutation response for {method.upper()} {path} is not valid JSON"
            ) from exc
        if not isinstance(payload, Mapping):
            raise ProviderResponseValidationError(
                f"live mutation response for {method.upper()} {path} is not a JSON object"
            )
        return dict(payload)

    def _build_ssl_context(self) -> ssl.SSLContext:
        # Verification is the explicit pin check in _enforce_pin, executed
        # before any request bytes (credentials) are sent.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    def _enforce_pin(self, connection: Any) -> None:
        sock = getattr(connection, "sock", None)
        cert_der = sock.getpeercert(binary_form=True) if sock is not None else None
        if not cert_der:
            raise ProviderTLSVerificationError(
                "live mutation peer presented no certificate; credentials were not sent"
            )
        observed = sha256_fingerprint_for_der(cert_der)
        if observed != self._pinned_sha256:
            raise ProviderTLSVerificationError(
                "live mutation certificate fingerprint mismatch; credentials were not sent"
            )


__all__ = [
    "PinnedMutatingHTTPSJSONClient",
]
