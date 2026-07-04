"""Safety gates for the live MUTATION transports.

Two invariants anchor this file:

(a) the read-path transports remain structurally unable to mutate, and
(b) every concrete mutating verb is refused fail-closed without a verified
    ACT clearance proof handle.

No test opens a socket or resolves a credential.
"""

import inspect

import pytest

from agentickvm.providers import mutation_gate as mutation_gate_module
from agentickvm.providers import pikvm_mutation_transport as pikvm_mutation_module
from agentickvm.providers import redfish_mutation_transport as redfish_mutation_module
from agentickvm.providers.errors import ProviderMutationBlockedError
from agentickvm.providers.mutation_gate import MutationClearanceLedger
from agentickvm.providers.pikvm_mutation_transport import (
    PIKVM_LIVE_MUTATING_OPERATIONS,
    LivePiKVMMutationTransport,
)
from agentickvm.providers.pikvm_transport import (
    PiKVMAuthenticatedHTTPClient,
    PiKVMCredentialRef,
    PiKVMTargetConfig,
)
from agentickvm.providers.redfish_mutation_transport import (
    REDFISH_LIVE_MUTATING_OPERATIONS,
    LiveRedfishMutationTransport,
)
from agentickvm.providers.redfish_transport import (
    REDFISH_LIVE_READ_OPERATIONS,
    LiveRedfishReadTransport,
    RedfishCredentialRef,
    RedfishHTTPReadClient,
    RedfishTargetConfig,
)

GOOD_FINGERPRINT = "aa" * 32


class _StaticProbe:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint

    def certificate_der_sha256(self, *, host: str, port: int, timeout_seconds: float) -> str:
        return self.fingerprint


class _NullReadClient:
    trust = None

    def get_json(self, path, *, timeout_seconds):
        return {}


class _RefusingMutationClientFactory:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, config, credential_ref, trust, clearance):
        self.calls += 1
        raise AssertionError("mutating client must never be built without clearance")


def _read_transport() -> LiveRedfishReadTransport:
    return LiveRedfishReadTransport(
        config=RedfishTargetConfig(
            base_url="https://redfish.example.invalid",
            cert_fingerprint=GOOD_FINGERPRINT,
        ),
        credential_ref=RedfishCredentialRef("env://REDFISH_LAB"),
        tls_probe=_StaticProbe(GOOD_FINGERPRINT),
        http_client_factory=lambda config, ref, trust: _NullReadClient(),
    )


def test_read_transport_still_refuses_every_mutating_verb() -> None:
    transport = _read_transport()

    for verb in (transport.reset, transport.set_boot_override, transport.bmc_reset):
        with pytest.raises(ProviderMutationBlockedError):
            verb()


def test_read_client_protocols_expose_no_mutating_surface() -> None:
    for protocol in (RedfishHTTPReadClient, PiKVMAuthenticatedHTTPClient):
        members = {name for name in dir(protocol) if not name.startswith("_")}
        assert "post_json" not in members
        assert "patch_json" not in members
        assert "get_json" in members


def test_mutating_and_read_operation_sets_are_disjoint() -> None:
    assert not REDFISH_LIVE_MUTATING_OPERATIONS & REDFISH_LIVE_READ_OPERATIONS
    assert all(
        operation.startswith(("power.", "boot."))
        for operation in REDFISH_LIVE_MUTATING_OPERATIONS | PIKVM_LIVE_MUTATING_OPERATIONS
    )


def test_mutating_transports_refuse_fail_closed_without_verified_clearance() -> None:
    redfish_factory = _RefusingMutationClientFactory()
    redfish = LiveRedfishMutationTransport(
        config=RedfishTargetConfig(
            base_url="https://redfish.example.invalid",
            cert_fingerprint=GOOD_FINGERPRINT,
        ),
        credential_ref=RedfishCredentialRef("env://REDFISH_LAB"),
        target_id="lab-node-fixture",
        provider_id="redfish-live-fixture",
        system_path="/redfish/v1/Systems/1",
        tls_probe=_StaticProbe(GOOD_FINGERPRINT),
        http_client_factory=redfish_factory,
    )
    pikvm_factory = _RefusingMutationClientFactory()
    pikvm = LivePiKVMMutationTransport(
        config=PiKVMTargetConfig(
            base_url="https://pikvm.example.invalid",
            cert_fingerprint=GOOD_FINGERPRINT,
        ),
        credential_ref=PiKVMCredentialRef("env://PIKVM_LAB"),
        target_id="pikvm-node-fixture",
        provider_id="pikvm-live-fixture",
        tls_probe=_StaticProbe(GOOD_FINGERPRINT),
        http_client_factory=pikvm_factory,
    )

    for call in (
        lambda: redfish.power_on(clearance=None),
        lambda: redfish.power_force_off(clearance=None),
        lambda: redfish.power_cycle(clearance=None),
        lambda: redfish.set_boot_override(boot_target="Pxe", clearance=None),
        lambda: pikvm.power_on(clearance=None),
        lambda: pikvm.power_force_off(clearance=None),
        lambda: pikvm.power_cycle(clearance=None),
    ):
        with pytest.raises(ProviderMutationBlockedError):
            call()

    assert redfish_factory.calls == 0
    assert pikvm_factory.calls == 0


def test_mutation_gate_ledger_is_fail_closed_for_unknown_objects() -> None:
    ledger = MutationClearanceLedger()

    with pytest.raises(ProviderMutationBlockedError):
        ledger.consume(object(), now=None)


def test_mutation_provider_modules_have_no_live_io_imports() -> None:
    source = "\n".join(
        [
            inspect.getsource(mutation_gate_module),
            inspect.getsource(redfish_mutation_module),
            inspect.getsource(pikvm_mutation_module),
        ]
    )

    forbidden_imports = (
        "import requests",
        "from requests",
        "import urllib",
        "from urllib",
        "import http.client",
        "from http.client",
        "import socket",
        "from socket",
        "import ssl",
        "from ssl",
    )
    for item in forbidden_imports:
        assert item not in source
