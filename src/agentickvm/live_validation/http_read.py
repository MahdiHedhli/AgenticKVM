"""Shared GET-only HTTPS JSON client for operator-run live validation.

This module contains real network primitives (``ssl`` + ``http.client``) and
therefore lives outside the provider package, next to the existing
``RealTLSPiKVMProbe``. Provider modules must never import it; automated tests
exercise it only through injected fake connection factories.

Safety posture:

- Only the GET method exists on this surface; any other method fails closed
  with ``ProviderMutationBlockedError`` before a connection is opened.
- TLS is either fully verified (``ssl.create_default_context``) or pinned to
  an operator-supplied SHA-256 certificate fingerprint that is checked after
  the handshake and before any request bytes (credentials) are sent.
- Credential material is resolved from explicit references (``env://`` or
  ``file://``); raw values never appear in errors, logs, or ``repr``.
"""

from __future__ import annotations

import json
import ssl
from collections.abc import Callable, Mapping
from http.client import HTTPSConnection
from pathlib import Path
from typing import Any

from agentickvm.providers.errors import (
    ProviderAuthenticationFailedError,
    ProviderAuthenticationRequiredError,
    ProviderConnectionError,
    ProviderMutationBlockedError,
    ProviderProtocolError,
    ProviderResponseValidationError,
    ProviderTLSVerificationError,
)
from agentickvm.providers.pikvm_transport import (
    normalize_cert_fingerprint,
    sha256_fingerprint_for_der,
)
from agentickvm.providers.transport_policy import TransportSecurityPolicy

# A connection factory returns an HTTPSConnection-compatible object. Tests
# inject fakes here so no socket is ever created.
HTTPSConnectionFactory = Callable[[str, int, ssl.SSLContext | None, float], Any]

_ENV_SCHEME = "env://"
_FILE_SCHEME = "file://"
_USERNAME_SUFFIXES = ("_USERNAME", "_USER")
_PASSWORD_SUFFIXES = ("_PASSWORD", "_PASS")


def resolve_credential_pair(
    credential_ref: str,
    *,
    env: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    """Resolve a credential reference to a (username, password) pair.

    Supported reference schemes:

    - ``env://PREFIX`` reads ``PREFIX_USERNAME``/``PREFIX_USER`` and
      ``PREFIX_PASSWORD``/``PREFIX_PASS`` from the provided environment
      mapping (or ``os.environ`` when omitted).
    - ``file:///abs/path`` reads a JSON object with ``username`` and
      ``password`` keys from an operator-managed file outside the repository.

    Errors never include the reference or any resolved value.
    """

    if env is None:
        import os

        env = os.environ
    if credential_ref.startswith(_ENV_SCHEME):
        prefix = credential_ref.removeprefix(_ENV_SCHEME).strip("/")
        if not prefix:
            raise ProviderAuthenticationRequiredError(
                "env credential_ref requires a variable prefix"
            )
        username = _first_env(env, prefix, _USERNAME_SUFFIXES)
        password = _first_env(env, prefix, _PASSWORD_SUFFIXES)
        if not username or not password:
            raise ProviderAuthenticationRequiredError(
                "env credential_ref did not resolve to a username and password"
            )
        return username, password
    if credential_ref.startswith(_FILE_SCHEME):
        path = Path(credential_ref.removeprefix(_FILE_SCHEME))
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ProviderAuthenticationRequiredError(
                "file credential_ref does not exist"
            ) from exc
        except (OSError, ValueError) as exc:
            raise ProviderAuthenticationRequiredError(
                "file credential_ref is unreadable or not valid JSON"
            ) from exc
        if not isinstance(payload, Mapping):
            raise ProviderAuthenticationRequiredError(
                "file credential_ref must contain a JSON object"
            )
        username = str(payload.get("username", ""))
        password = str(payload.get("password", ""))
        if not username or not password:
            raise ProviderAuthenticationRequiredError(
                "file credential_ref must provide username and password"
            )
        return username, password
    raise ProviderAuthenticationRequiredError(
        "unsupported credential_ref scheme; use env:// or file://"
    )


def _first_env(env: Mapping[str, str], prefix: str, suffixes: tuple[str, ...]) -> str:
    for suffix in suffixes:
        value = env.get(prefix + suffix, "")
        if value:
            return value
    return ""


def default_https_connection_factory(
    host: str,
    port: int,
    context: ssl.SSLContext | None,
    timeout_seconds: float,
) -> HTTPSConnection:
    """Build a real HTTPS connection (operator-run paths only)."""

    return HTTPSConnection(host, port=port, timeout=timeout_seconds, context=context)


class GETOnlyHTTPSJSONClient:
    """HTTPS JSON client that can only ever issue GET requests.

    The pinned-fingerprint mode connects with certificate verification
    delegated to an explicit post-handshake SHA-256 pin check that runs before
    any request (and therefore any credential header) is transmitted.
    """

    def __init__(
        self,
        *,
        host: str,
        port: int,
        headers: Mapping[str, str],
        pinned_sha256: str | None,
        verify_tls: bool,
        policy: TransportSecurityPolicy | None = None,
        connection_factory: HTTPSConnectionFactory | None = None,
    ) -> None:
        if pinned_sha256 is None and not verify_tls:
            raise ProviderProtocolError(
                "unverified TLS without a pinned fingerprint is refused"
            )
        self._host = host
        self._port = port
        self._headers = dict(headers)
        self._pinned_sha256 = (
            normalize_cert_fingerprint(pinned_sha256) if pinned_sha256 else None
        )
        self._verify_tls = verify_tls
        self.policy = policy or TransportSecurityPolicy()
        self._connection_factory = connection_factory or default_https_connection_factory

    def __repr__(self) -> str:  # pragma: no cover - shape guard only
        return (
            f"<{type(self).__name__} host=[REDACTED] "
            f"pinned={bool(self._pinned_sha256)} verify_tls={self._verify_tls}>"
        )

    def get_json(self, path: str, *, timeout_seconds: float) -> Mapping[str, Any]:
        """Return the JSON object at ``path`` via a read-only GET."""

        return self.request_json("GET", path, timeout_seconds=timeout_seconds)

    def request_json(
        self,
        method: str,
        path: str,
        *,
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        """Fail closed for every method except GET, then perform the read."""

        if method.upper() != "GET":
            raise ProviderMutationBlockedError(
                "live read client refuses non-GET methods; mutating operations "
                "are not implemented"
            )
        if not path.startswith("/"):
            raise ProviderProtocolError("live read client requires absolute paths")
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
                connection.request("GET", path, headers=dict(self._headers))
                response = connection.getresponse()
                status = int(response.status)
                body = response.read(self.policy.max_response_bytes + 1)
                content_type = str(response.getheader("Content-Type") or "")
            except (ProviderTLSVerificationError, ProviderProtocolError):
                raise
            except (OSError, ssl.SSLError) as exc:
                raise ProviderConnectionError(
                    f"live read connection failed for GET {path}"
                ) from exc
        finally:
            try:
                connection.close()
            except Exception:  # noqa: BLE001 - close must never mask the real error
                pass
        if status in (401, 403):
            raise ProviderAuthenticationFailedError(
                f"live read authentication failed with status {status} for GET {path}"
            )
        if status >= 300:
            raise ProviderProtocolError(
                f"live read request failed with status {status} for GET {path}"
            )
        if len(body) > self.policy.max_response_bytes:
            raise ProviderResponseValidationError(
                f"live read response exceeded {self.policy.max_response_bytes} bytes"
            )
        if content_type and "json" not in content_type.lower():
            raise ProviderResponseValidationError(
                f"live read response for GET {path} is not JSON"
            )
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise ProviderResponseValidationError(
                f"live read response for GET {path} is not valid JSON"
            ) from exc
        if not isinstance(payload, Mapping):
            raise ProviderResponseValidationError(
                f"live read response for GET {path} is not a JSON object"
            )
        return dict(payload)

    def _build_ssl_context(self) -> ssl.SSLContext:
        if self._pinned_sha256 is not None:
            # Verification is the explicit pin check in _enforce_pin, executed
            # before any request bytes (credentials) are sent.
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
        return ssl.create_default_context()

    def _enforce_pin(self, connection: Any) -> None:
        if self._pinned_sha256 is None:
            return
        sock = getattr(connection, "sock", None)
        cert_der = sock.getpeercert(binary_form=True) if sock is not None else None
        if not cert_der:
            raise ProviderTLSVerificationError(
                "live read peer presented no certificate; credentials were not sent"
            )
        observed = sha256_fingerprint_for_der(cert_der)
        if observed != self._pinned_sha256:
            raise ProviderTLSVerificationError(
                "live read certificate fingerprint mismatch; credentials were not sent"
            )


__all__ = [
    "GETOnlyHTTPSJSONClient",
    "HTTPSConnectionFactory",
    "default_https_connection_factory",
    "resolve_credential_pair",
]
