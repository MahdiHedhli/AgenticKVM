"""Operator-run live Redfish READ transport wiring.

This module provides the only real network implementations behind the
socket-free ``agentickvm.providers.redfish_transport`` seam:

- ``RealTLSRedfishProbe`` captures the BMC certificate fingerprint without
  sending credentials (pin bootstrap, mirrors ``RealTLSPiKVMProbe``).
- ``RealRedfishHTTPReadClient`` satisfies ``RedfishHTTPReadClient`` using the
  shared GET-only HTTPS JSON client with HTTP Basic authentication.

Nothing in this module is imported by providers or exercised live in CI;
automated tests inject fake connection factories. Mutating Redfish verbs do
not exist on this surface and the underlying client refuses non-GET methods.
"""

from __future__ import annotations

import base64
import socket
import ssl
from collections.abc import Mapping
from typing import Any

from agentickvm.live_validation.http_read import (
    GETOnlyHTTPSJSONClient,
    HTTPSConnectionFactory,
    resolve_credential_pair,
)
from agentickvm.providers.errors import ProviderError
from agentickvm.providers.pikvm_transport import sha256_fingerprint_for_der
from agentickvm.providers.redfish_transport import (
    LiveRedfishReadTransport,
    RedfishCredentialRef,
    RedfishHTTPClientFactory,
    RedfishPinnedTrust,
    RedfishTargetConfig,
    RedfishTLSProbe,
)


class RedfishLiveValidationError(RuntimeError):
    """Raised when a live Redfish read precondition is unsafe."""


class RealTLSRedfishProbe:
    """Unauthenticated TLS probe for BMC certificate fingerprint capture.

    BMCs commonly present self-signed certificates, so this probe performs the
    handshake without chain verification purely to observe the certificate.
    No credentials or application data cross this connection; the captured
    fingerprint feeds the pin check that gates the authenticated client.
    """

    def certificate_der_sha256(
        self,
        *,
        host: str,
        port: int,
        timeout_seconds: float,
    ) -> str:
        """Return the peer certificate SHA-256 fingerprint without credentials."""

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=timeout_seconds) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls:
                cert_der = tls.getpeercert(binary_form=True)
        if not cert_der:
            raise RedfishLiveValidationError("Redfish peer did not present a certificate")
        return sha256_fingerprint_for_der(cert_der)


class RealRedfishHTTPReadClient:
    """``RedfishHTTPReadClient`` backed by the shared GET-only HTTPS client."""

    def __init__(
        self,
        *,
        trust: RedfishPinnedTrust | None,
        client: GETOnlyHTTPSJSONClient,
    ) -> None:
        self.trust = trust
        self._client = client

    def get_json(self, path: str, *, timeout_seconds: float) -> Mapping[str, Any]:
        return self._client.get_json(path, timeout_seconds=timeout_seconds)


def redfish_http_client_factory(
    *,
    env: Mapping[str, str] | None = None,
    connection_factory: HTTPSConnectionFactory | None = None,
) -> RedfishHTTPClientFactory:
    """Return a factory building Basic-auth read clients for the transport.

    Credentials are resolved from the credential reference only at build time
    (after the TLS pin preflight has passed) and exist solely inside the
    Authorization header of the underlying client.
    """

    def _build(
        config: RedfishTargetConfig,
        credential_ref: RedfishCredentialRef,
        trust: RedfishPinnedTrust | None,
    ) -> RealRedfishHTTPReadClient:
        username, password = resolve_credential_pair(credential_ref.value, env=env)
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        client = GETOnlyHTTPSJSONClient(
            host=config.host,
            port=config.port,
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
            },
            pinned_sha256=trust.sha256_fingerprint if trust else None,
            verify_tls=config.verify_ssl,
            connection_factory=connection_factory,
        )
        return RealRedfishHTTPReadClient(trust=trust, client=client)

    return _build


def build_live_redfish_read_transport(
    *,
    base_url: str,
    credential_ref: str,
    cert_fingerprint: str | None,
    verify_ssl: bool,
    tls_probe: RedfishTLSProbe | None = None,
    http_client_factory: RedfishHTTPClientFactory | None = None,
) -> LiveRedfishReadTransport:
    """Build the read-only live transport for an operator-run session."""

    return LiveRedfishReadTransport(
        config=RedfishTargetConfig(
            base_url=base_url,
            cert_fingerprint=cert_fingerprint,
            verify_ssl=verify_ssl,
        ),
        credential_ref=RedfishCredentialRef(credential_ref),
        tls_probe=tls_probe or RealTLSRedfishProbe(),
        http_client_factory=http_client_factory or redfish_http_client_factory(),
    )


def collect_redfish_read_evidence(
    transport: LiveRedfishReadTransport,
) -> dict[str, Any]:
    """Run every supported read operation and return a redacted evidence map.

    Each operation is attempted independently; failures are recorded with the
    error's public (redacted) message so a partial pass still yields evidence.
    """

    operations = {
        "observe.status": transport.status,
        "observe.power_state": transport.power_state,
        "observe.boot_status": transport.boot_status,
        "observe.hardware_inventory": transport.hardware_inventory,
        "observe.sensors": transport.sensors,
        "observe.event_logs": transport.event_logs,
    }
    evidence: dict[str, Any] = {}
    for operation, runner in operations.items():
        try:
            evidence[operation] = {"ok": True, "data": _to_plain(runner())}
        except ProviderError as exc:
            evidence[operation] = {"ok": False, "error": exc.public_message}
    return evidence


def _to_plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _to_plain(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain(item) for item in value]
    return value


__all__ = [
    "RealRedfishHTTPReadClient",
    "RealTLSRedfishProbe",
    "RedfishLiveValidationError",
    "build_live_redfish_read_transport",
    "collect_redfish_read_evidence",
    "redfish_http_client_factory",
]
