"""Fixture tests for the socket-free Redfish live read transport seam.

No test here opens a socket, resolves a credential, or contacts hardware; the
TLS probe and HTTP read client are injected fakes, exactly like the PiKVM
observe transport tests.
"""

import inspect

import pytest

from agentickvm.providers import redfish_transport as transport_module
from agentickvm.providers.errors import (
    ProviderAuthenticationRequiredError,
    ProviderMutationBlockedError,
    ProviderProtocolError,
    ProviderResponseValidationError,
)
from agentickvm.providers.redfish_transport import (
    LiveRedfishReadTransport,
    REDFISH_LIVE_READ_OPERATIONS,
    REDFISH_SERVICE_ROOT_PATH,
    RedfishCredentialRef,
    RedfishFingerprintMismatchError,
    RedfishPinnedTrust,
    RedfishTargetConfig,
)
from agentickvm.providers.pikvm_transport import normalize_cert_fingerprint

GOOD_FINGERPRINT = "aa" * 32
BAD_FINGERPRINT = "bb" * 32

SUPERMICRO_SHAPED_ROUTES = {
    REDFISH_SERVICE_ROOT_PATH: {
        "RedfishVersion": "1.9.0",
        "Systems": {"@odata.id": "/redfish/v1/Systems"},
        "Managers": {"@odata.id": "/redfish/v1/Managers"},
        "Chassis": {"@odata.id": "/redfish/v1/Chassis"},
    },
    "/redfish/v1/Systems": {
        "Members": [{"@odata.id": "/redfish/v1/Systems/1"}],
        "Members@odata.count": 1,
    },
    "/redfish/v1/Systems/1": {
        "Id": "1",
        "Name": "System",
        "Manufacturer": "Supermicro",
        "Model": "Fixture-X11",
        "BiosVersion": "3.4",
        "PowerState": "On",
        "Status": {"State": "Enabled", "Health": "OK"},
        "Boot": {
            "BootSourceOverrideTarget": "None",
            "BootSourceOverrideEnabled": "Disabled",
        },
        "ProcessorSummary": {"Count": 1},
        "MemorySummary": {"TotalSystemMemoryGiB": 32},
    },
    "/redfish/v1/Managers": {
        "Members": [{"@odata.id": "/redfish/v1/Managers/1"}],
    },
    "/redfish/v1/Managers/1": {
        "Id": "1",
        "Name": "Manager",
        "Status": {"State": "Enabled", "Health": "OK"},
        "LogServices": {"@odata.id": "/redfish/v1/Managers/1/LogServices"},
    },
    "/redfish/v1/Managers/1/LogServices": {
        "Members": [{"@odata.id": "/redfish/v1/Managers/1/LogServices/Log1"}],
    },
    "/redfish/v1/Managers/1/LogServices/Log1": {
        "Id": "Log1",
        "Entries": {"@odata.id": "/redfish/v1/Managers/1/LogServices/Log1/Entries"},
    },
    "/redfish/v1/Managers/1/LogServices/Log1/Entries": {
        "Members": [{"Severity": "OK", "Message": "Fixture event entry"}],
    },
    "/redfish/v1/Chassis": {
        "Members": [{"@odata.id": "/redfish/v1/Chassis/1"}],
    },
    "/redfish/v1/Chassis/1": {
        "Id": "1",
        "Thermal": {"@odata.id": "/redfish/v1/Chassis/1/Thermal"},
    },
    "/redfish/v1/Chassis/1/Thermal": {
        "Temperatures": [
            {"Name": "CPU Temp", "ReadingCelsius": 41, "Status": {"Health": "OK"}}
        ],
        "Fans": [{"Name": "FAN1", "Reading": 4200, "Status": {"Health": "OK"}}],
    },
}


class MockTLSProbe:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint
        self.calls = []

    def certificate_der_sha256(self, *, host: str, port: int, timeout_seconds: float) -> str:
        self.calls.append({"host": host, "port": port, "timeout_seconds": timeout_seconds})
        return self.fingerprint


class MockRedfishHTTPReadClient:
    def __init__(self, *, trust: RedfishPinnedTrust | None, routes=None) -> None:
        self.trust = trust
        self.calls = []
        self.routes = dict(SUPERMICRO_SHAPED_ROUTES if routes is None else routes)

    def get_json(self, path: str, *, timeout_seconds: float):
        self.calls.append({"path": path, "timeout_seconds": timeout_seconds})
        try:
            return self.routes[path]
        except KeyError as exc:
            raise ProviderResponseValidationError(f"no mock route for {path}") from exc


class RecordingFactory:
    def __init__(self, routes=None) -> None:
        self.credential_received = None
        self.trust_received = None
        self.client = None
        self.routes = routes

    def __call__(self, config, credential_ref, trust):
        self.credential_received = credential_ref
        self.trust_received = trust
        self.client = MockRedfishHTTPReadClient(trust=trust, routes=self.routes)
        return self.client


def _transport(factory: RecordingFactory | None = None) -> LiveRedfishReadTransport:
    return LiveRedfishReadTransport(
        config=RedfishTargetConfig(
            base_url="https://redfish.example.invalid",
            cert_fingerprint=GOOD_FINGERPRINT,
            verify_ssl=False,
        ),
        credential_ref=RedfishCredentialRef("env://REDFISH_LAB"),
        tls_probe=MockTLSProbe(GOOD_FINGERPRINT),
        http_client_factory=factory or RecordingFactory(),
    )


def test_redfish_target_config_requires_https_and_pin_posture() -> None:
    with pytest.raises(ProviderProtocolError, match="https"):
        RedfishTargetConfig(base_url="http://redfish.example.invalid")
    with pytest.raises(ProviderProtocolError, match="pinning"):
        RedfishTargetConfig(
            base_url="https://redfish.example.invalid",
            cert_fingerprint=None,
            verify_ssl=False,
        )


def test_redfish_target_config_extracts_port_from_base_url() -> None:
    config = RedfishTargetConfig(base_url="https://redfish.example.invalid:8443")

    assert config.host == "redfish.example.invalid"
    assert config.port == 8443


def test_redfish_credential_ref_rejects_raw_secrets_and_redacts_label() -> None:
    with pytest.raises(ProviderAuthenticationRequiredError):
        RedfishCredentialRef("password=hunter2")
    with pytest.raises(ProviderAuthenticationRequiredError):
        RedfishCredentialRef("")

    ref = RedfishCredentialRef("env://REDFISH_LAB")
    assert ref.safe_label() == "[CREDENTIAL_REF]"
    assert "REDFISH_LAB" not in repr(ref)


def test_redfish_cert_preflight_match_builds_client_with_pinned_trust() -> None:
    factory = RecordingFactory()
    transport = _transport(factory)

    assert factory.credential_received.safe_label() == "[CREDENTIAL_REF]"
    assert factory.trust_received.sha256_fingerprint == normalize_cert_fingerprint(
        GOOD_FINGERPRINT
    )
    assert transport.http.trust == factory.trust_received


def test_redfish_cert_preflight_mismatch_aborts_before_credentials() -> None:
    factory = RecordingFactory()

    with pytest.raises(RedfishFingerprintMismatchError):
        LiveRedfishReadTransport(
            config=RedfishTargetConfig(
                base_url="https://redfish.example.invalid",
                cert_fingerprint=GOOD_FINGERPRINT,
                verify_ssl=False,
            ),
            credential_ref=RedfishCredentialRef("env://REDFISH_LAB"),
            tls_probe=MockTLSProbe(BAD_FINGERPRINT),
            http_client_factory=factory,
        )

    assert factory.credential_received is None
    assert factory.client is None


def test_redfish_read_operations_discover_supermicro_shaped_paths() -> None:
    factory = RecordingFactory()
    transport = _transport(factory)

    assert transport.power_state()["power_state"] == "On"
    assert transport.boot_status()["boot_source_override"] == "None"
    inventory = transport.hardware_inventory()
    assert inventory["system_id"] == "1"
    assert inventory["model"] == "Fixture-X11"
    sensors = transport.sensors()
    assert sensors["source"] == "thermal"
    assert sensors["temperatures"][0]["ReadingCelsius"] == 41
    events = transport.event_logs()
    assert events["log_service_id"] == "Log1"
    assert events["events"][0]["Message"] == "Fixture event entry"
    status = transport.status()
    assert status["manager"]["Id"] == "1"
    assert {call["path"] for call in factory.client.calls} >= {
        "/redfish/v1/Systems/1",
        "/redfish/v1/Chassis/1/Thermal",
        "/redfish/v1/Managers/1/LogServices/Log1/Entries",
    }


def test_redfish_live_read_operation_set_is_observe_only() -> None:
    assert all(item.startswith("observe.") for item in REDFISH_LIVE_READ_OPERATIONS)


def test_redfish_transport_refuses_every_mutating_verb() -> None:
    transport = _transport()

    with pytest.raises(ProviderMutationBlockedError):
        transport.reset(reset_type="ForceRestart")
    with pytest.raises(ProviderMutationBlockedError):
        transport.set_boot_override(target="Pxe")
    with pytest.raises(ProviderMutationBlockedError):
        transport.bmc_reset()

    # Refusal happens before any HTTP call reaches the injected client.
    mutating_paths = [
        call["path"]
        for call in transport.http.calls
        if "Actions" in call["path"] or "Reset" in call["path"]
    ]
    assert mutating_paths == []


def test_redfish_transport_redacts_sensitive_read_payload_fields() -> None:
    routes = dict(SUPERMICRO_SHAPED_ROUTES)
    routes["/redfish/v1/Managers/1"] = {
        "Id": "1",
        "Name": "Manager",
        "HostName": "bmc-lab.internal",
        "session_cookie": "cookie-value",
        "LogServices": {"@odata.id": "/redfish/v1/Managers/1/LogServices"},
    }
    transport = _transport(RecordingFactory(routes))

    manager = transport.manager_status()

    assert manager["HostName"] == "[REDACTED]"
    assert manager["session_cookie"] == "[REDACTED]"
    assert "bmc-lab.internal" not in repr(manager)
    assert "cookie-value" not in repr(manager)


def test_redfish_transport_reads_no_env_secrets(monkeypatch) -> None:
    monkeypatch.setenv("REDFISH_LAB_PASSWORD", "must-not-leak-provider-secret")
    transport = _transport()

    result = {
        "power": transport.power_state(),
        "inventory": transport.hardware_inventory(),
    }

    assert "must-not-leak-provider-secret" not in repr(result)


def test_redfish_transport_missing_collections_fail_closed() -> None:
    routes = {REDFISH_SERVICE_ROOT_PATH: {"RedfishVersion": "1.9.0"}}
    transport = _transport(RecordingFactory(routes))

    with pytest.raises(ProviderResponseValidationError, match="Systems"):
        transport.power_state()
    with pytest.raises(ProviderResponseValidationError, match="Managers"):
        transport.event_logs()


def test_redfish_transport_module_has_no_live_io_imports() -> None:
    source = inspect.getsource(transport_module)

    for item in (
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
    ):
        assert item not in source
