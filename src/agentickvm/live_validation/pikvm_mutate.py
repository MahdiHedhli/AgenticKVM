"""Operator-run live PiKVM ATX MUTATION transport wiring.

The real network implementations behind the socket-free
``agentickvm.providers.pikvm_mutation_transport`` seam. Nothing here is
imported by providers or exercised live in CI; automated tests inject fake
connection factories, and live mutating use is reserved for the supervised
operator demo.

Credentials (kvmd ``X-KVMD-User`` / ``X-KVMD-Passwd`` headers) are resolved
only inside the mutation client factory, which refuses to run without a
verified mutation clearance handle and a pinned trust root.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Callable

from agentickvm.live_validation.http_mutate import PinnedMutatingHTTPSJSONClient
from agentickvm.live_validation.http_read import (
    HTTPSConnectionFactory,
    resolve_credential_pair,
)
from agentickvm.live_validation.pikvm import RealTLSPiKVMProbe
from agentickvm.providers.errors import ProviderMutationBlockedError
from agentickvm.providers.mutation_gate import (
    MutationClearanceLedger,
    VerifiedMutationClearance,
)
from agentickvm.providers.pikvm_mutation_transport import (
    LivePiKVMMutationTransport,
    PiKVMMutationHTTPClientFactory,
)
from agentickvm.providers.pikvm_transport import (
    PiKVMCredentialRef,
    PiKVMPinnedTrust,
    PiKVMTargetConfig,
    PiKVMTLSProbe,
)


class RealPiKVMHTTPMutationClient:
    """``PiKVMHTTPMutationClient`` backed by the shared pinned mutation client."""

    def __init__(
        self,
        *,
        trust: PiKVMPinnedTrust,
        client: PinnedMutatingHTTPSJSONClient,
    ) -> None:
        self.trust = trust
        self._client = client

    def post_json(
        self, path: str, body: Mapping[str, Any], *, timeout_seconds: float
    ) -> Mapping[str, Any]:
        return self._client.post_json(path, body, timeout_seconds=timeout_seconds)


def pikvm_mutating_http_client_factory(
    *,
    env: Mapping[str, str] | None = None,
    connection_factory: HTTPSConnectionFactory | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> PiKVMMutationHTTPClientFactory:
    """Return a factory building kvmd-auth mutation clients for the transport.

    The factory fails closed before resolving any credential when the pinned
    trust root or the verified clearance handle is missing or not genuine.
    """

    def _build(
        config: PiKVMTargetConfig,
        credential_ref: PiKVMCredentialRef,
        trust: PiKVMPinnedTrust | None,
        clearance: object,
    ) -> RealPiKVMHTTPMutationClient:
        if trust is None:
            raise ProviderMutationBlockedError(
                "mutating PiKVM client factory requires a pinned trust root"
            )
        if not isinstance(clearance, VerifiedMutationClearance):
            raise ProviderMutationBlockedError(
                "mutating PiKVM client factory requires a verified mutation "
                "clearance handle; credentials were not resolved"
            )
        username, password = resolve_credential_pair(credential_ref.value, env=env)
        client = PinnedMutatingHTTPSJSONClient(
            host=config.host,
            port=config.port,
            headers={
                "X-KVMD-User": username,
                "X-KVMD-Passwd": password,
                "Accept": "application/json",
            },
            pinned_sha256=trust.sha256_fingerprint,
            clearance=clearance,
            connection_factory=connection_factory,
            now_factory=now_factory,
        )
        return RealPiKVMHTTPMutationClient(trust=trust, client=client)

    return _build


def build_live_pikvm_mutation_transport(
    *,
    base_url: str,
    credential_ref: str,
    cert_fingerprint: str | None,
    target_id: str,
    provider_id: str,
    tls_probe: PiKVMTLSProbe | None = None,
    http_client_factory: PiKVMMutationHTTPClientFactory | None = None,
    ledger: MutationClearanceLedger | None = None,
    now_factory: Callable[[], datetime] | None = None,
) -> LivePiKVMMutationTransport:
    """Build the clearance-gated ATX mutation transport for an operator session.

    Unlike the observe path, ``cert_fingerprint`` is mandatory: mutation is
    refused without a pinned trust root.
    """

    if not cert_fingerprint:
        raise ProviderMutationBlockedError(
            "live PiKVM mutation transport requires a pinned certificate fingerprint"
        )
    return LivePiKVMMutationTransport(
        config=PiKVMTargetConfig(
            base_url=base_url,
            cert_fingerprint=cert_fingerprint,
            verify_ssl=False,
        ),
        credential_ref=PiKVMCredentialRef(credential_ref),
        target_id=target_id,
        provider_id=provider_id,
        tls_probe=tls_probe or RealTLSPiKVMProbe(),
        http_client_factory=http_client_factory or pikvm_mutating_http_client_factory(),
        ledger=ledger,
        now_factory=now_factory,
    )


__all__ = [
    "RealPiKVMHTTPMutationClient",
    "build_live_pikvm_mutation_transport",
    "pikvm_mutating_http_client_factory",
]
