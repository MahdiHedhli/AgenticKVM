"""Operator-run live Redfish MUTATION transport wiring.

The real network implementations behind the socket-free
``agentickvm.providers.redfish_mutation_transport`` seam. Nothing here is
imported by providers or exercised live in CI; automated tests inject fake
connection factories, and live mutating use is reserved for the supervised
operator demo.

Credentials are resolved from the credential reference only inside the
mutation client factory, which itself refuses to run without a verified
mutation clearance handle and a pinned trust root — so credential material
can only exist downstream of the Ed25519 clearance proof and the TLS pin
preflight.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Callable

from agentickvm.live_validation.http_mutate import PinnedMutatingHTTPSJSONClient
from agentickvm.live_validation.http_read import (
    HTTPSConnectionFactory,
    resolve_credential_pair,
)
from agentickvm.live_validation.redfish import RealTLSRedfishProbe
from agentickvm.providers.errors import ProviderMutationBlockedError
from agentickvm.providers.mutation_gate import (
    MutationClearanceLedger,
    VerifiedMutationClearance,
)
from agentickvm.providers.redfish_mutation_transport import (
    LiveRedfishMutationTransport,
    RedfishMutationHTTPClientFactory,
)
from agentickvm.providers.redfish_transport import (
    RedfishCredentialRef,
    RedfishPinnedTrust,
    RedfishTargetConfig,
    RedfishTLSProbe,
)


class RealRedfishHTTPMutationClient:
    """``RedfishHTTPMutationClient`` backed by the shared pinned mutation client."""

    def __init__(
        self,
        *,
        trust: RedfishPinnedTrust,
        client: PinnedMutatingHTTPSJSONClient,
    ) -> None:
        self.trust = trust
        self._client = client

    def post_json(
        self, path: str, body: Mapping[str, Any], *, timeout_seconds: float
    ) -> Mapping[str, Any]:
        return self._client.post_json(path, body, timeout_seconds=timeout_seconds)

    def patch_json(
        self, path: str, body: Mapping[str, Any], *, timeout_seconds: float
    ) -> Mapping[str, Any]:
        return self._client.patch_json(path, body, timeout_seconds=timeout_seconds)


def redfish_mutating_http_client_factory(
    *,
    env: Mapping[str, str] | None = None,
    connection_factory: HTTPSConnectionFactory | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> RedfishMutationHTTPClientFactory:
    """Return a factory building Basic-auth mutation clients for the transport.

    The factory fails closed before resolving any credential when the pinned
    trust root or the verified clearance handle is missing or not genuine.
    """

    def _build(
        config: RedfishTargetConfig,
        credential_ref: RedfishCredentialRef,
        trust: RedfishPinnedTrust | None,
        clearance: object,
    ) -> RealRedfishHTTPMutationClient:
        if trust is None:
            raise ProviderMutationBlockedError(
                "mutating Redfish client factory requires a pinned trust root"
            )
        if not isinstance(clearance, VerifiedMutationClearance):
            raise ProviderMutationBlockedError(
                "mutating Redfish client factory requires a verified mutation "
                "clearance handle; credentials were not resolved"
            )
        username, password = resolve_credential_pair(credential_ref.value, env=env)
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        client = PinnedMutatingHTTPSJSONClient(
            host=config.host,
            port=config.port,
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
            },
            pinned_sha256=trust.sha256_fingerprint,
            clearance=clearance,
            connection_factory=connection_factory,
            now_factory=now_factory,
        )
        return RealRedfishHTTPMutationClient(trust=trust, client=client)

    return _build


def build_live_redfish_mutation_transport(
    *,
    base_url: str,
    credential_ref: str,
    cert_fingerprint: str | None,
    target_id: str,
    provider_id: str,
    system_path: str,
    tls_probe: RedfishTLSProbe | None = None,
    http_client_factory: RedfishMutationHTTPClientFactory | None = None,
    ledger: MutationClearanceLedger | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> LiveRedfishMutationTransport:
    """Build the clearance-gated mutation transport for an operator session.

    Unlike the read builder, ``cert_fingerprint`` is mandatory: mutation is
    refused without a pinned trust root.
    """

    if not cert_fingerprint:
        raise ProviderMutationBlockedError(
            "live Redfish mutation transport requires a pinned certificate fingerprint"
        )
    return LiveRedfishMutationTransport(
        config=RedfishTargetConfig(
            base_url=base_url,
            cert_fingerprint=cert_fingerprint,
            verify_ssl=False,
        ),
        credential_ref=RedfishCredentialRef(credential_ref),
        target_id=target_id,
        provider_id=provider_id,
        system_path=system_path,
        tls_probe=tls_probe or RealTLSRedfishProbe(),
        http_client_factory=http_client_factory or redfish_mutating_http_client_factory(),
        ledger=ledger,
        now_factory=now_factory,
    )


__all__ = [
    "RealRedfishHTTPMutationClient",
    "build_live_redfish_mutation_transport",
    "redfish_mutating_http_client_factory",
]
