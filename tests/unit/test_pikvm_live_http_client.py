"""Fixture tests for the real PiKVM authenticated HTTP client.

The client satisfies the ``PiKVMAuthenticatedHTTPClient`` protocol using the
shared GET-only HTTPS layer with kvmd header authentication. All tests inject
fake connection factories; no socket is created and no real credential is
resolved.
"""

import json

import pytest

from agentickvm.live_validation.pikvm import (
    RealPiKVMAuthenticatedHTTPClient,
    pikvm_http_client_factory,
)
from agentickvm.providers.errors import (
    ProviderAuthenticationRequiredError,
    ProviderMutationBlockedError,
    ProviderTLSVerificationError,
)
from agentickvm.providers.pikvm_transport import (
    LivePiKVMObserveTransport,
    PIKVM_DEVICE_INFO_PATH,
    PIKVM_HEALTH_PATH,
    PIKVM_POWER_STATE_PATH,
    PIKVM_SCREENSHOT_METADATA_PATH,
    PIKVM_SCREEN_STATE_PATH,
    PiKVMCredentialRef,
    PiKVMTargetConfig,
)

from tests.unit.test_live_http_read_clients import (
    FAKE_CERT_FINGERPRINT,
    FakeConnection,
    FakeConnectionFactory,
    _StaticProbe,
)

SECRET_PASSWORD = "must-not-leak-live-secret"

PIKVM_ROUTES = {
    PIKVM_HEALTH_PATH: {"health": "ok"},
    PIKVM_SCREEN_STATE_PATH: {"kind": "mjpeg_snapshot", "sensitive": True},
    PIKVM_SCREENSHOT_METADATA_PATH: {
        "artifact": {"kind": "screenshot", "storage": "metadata-only"},
        "raw_bytes_included": False,
    },
    PIKVM_POWER_STATE_PATH: {"power_state": "on"},
    "/api/boot": {"boot_status": "os_running"},
    PIKVM_DEVICE_INFO_PATH: {"provider": "pikvm", "model": "v4-plus"},
}

CREDENTIAL_ENV = {
    "PIKVM_LAB_USERNAME": "admin",
    "PIKVM_LAB_PASSWORD": SECRET_PASSWORD,
}


def _live_transport(connection: FakeConnection) -> LivePiKVMObserveTransport:
    return LivePiKVMObserveTransport(
        config=PiKVMTargetConfig(
            base_url="https://pikvm.example.invalid",
            cert_fingerprint=FAKE_CERT_FINGERPRINT,
            verify_ssl=False,
        ),
        credential_ref=PiKVMCredentialRef("env://PIKVM_LAB"),
        tls_probe=_StaticProbe(FAKE_CERT_FINGERPRINT),
        http_client_factory=pikvm_http_client_factory(
            env=CREDENTIAL_ENV,
            connection_factory=FakeConnectionFactory(connection),
        ),
    )


def test_real_pikvm_client_satisfies_authenticated_client_protocol() -> None:
    connection = FakeConnection(routes=PIKVM_ROUTES)
    transport = _live_transport(connection)

    assert isinstance(transport.http, RealPiKVMAuthenticatedHTTPClient)
    # Protocol conformance: the attribute and method surface of
    # PiKVMAuthenticatedHTTPClient (not runtime_checkable) is present.
    assert hasattr(transport.http, "trust")
    assert callable(transport.http.get_json)
    assert transport.http.trust is not None
    assert transport.http.trust.sha256_fingerprint == FAKE_CERT_FINGERPRINT


def test_real_pikvm_client_sends_kvmd_headers_and_never_leaks_them() -> None:
    connection = FakeConnection(routes=PIKVM_ROUTES)
    transport = _live_transport(connection)

    health = transport.get_health()

    headers = connection.requests[0]["headers"]
    assert headers["X-KVMD-User"] == "admin"
    assert headers["X-KVMD-Passwd"] == SECRET_PASSWORD
    assert health["health"] == "ok"
    assert SECRET_PASSWORD not in repr(health)
    assert SECRET_PASSWORD not in repr(transport.http)
    assert SECRET_PASSWORD not in repr(transport.__dict__)


def test_real_pikvm_client_observe_surface_matches_live_transport_contract() -> None:
    connection = FakeConnection(routes=PIKVM_ROUTES)
    transport = _live_transport(connection)

    assert transport.get_health()["health"] == "ok"
    assert transport.get_screen_state()["kind"] == "mjpeg_snapshot"
    assert transport.get_screenshot_metadata()["raw_bytes_included"] is False
    assert transport.get_power_state()["power_state"] == "on"
    assert transport.get_boot_status()["boot_status"] == "os_running"
    assert transport.get_device_info()["provider"] == "pikvm"
    assert all(call["method"] == "GET" for call in connection.requests)


def test_real_pikvm_client_refuses_non_get_methods() -> None:
    connection = FakeConnection(routes=PIKVM_ROUTES)
    transport = _live_transport(connection)
    before = len(connection.requests)

    with pytest.raises(ProviderMutationBlockedError):
        transport.http._client.request_json(
            "POST", "/api/atx/power/on", timeout_seconds=1.0
        )

    assert len(connection.requests) == before


def test_real_pikvm_client_pin_mismatch_blocks_credential_headers() -> None:
    connection = FakeConnection(routes=PIKVM_ROUTES, cert_der=b"unexpected-cert")
    transport = _live_transport(connection)

    with pytest.raises(ProviderTLSVerificationError, match="credentials were not sent"):
        transport.get_health()

    assert connection.requests == []


def test_real_pikvm_factory_fails_closed_when_credentials_do_not_resolve() -> None:
    connection = FakeConnection(routes=PIKVM_ROUTES)

    with pytest.raises(ProviderAuthenticationRequiredError) as excinfo:
        LivePiKVMObserveTransport(
            config=PiKVMTargetConfig(
                base_url="https://pikvm.example.invalid",
                cert_fingerprint=FAKE_CERT_FINGERPRINT,
                verify_ssl=False,
            ),
            credential_ref=PiKVMCredentialRef("env://PIKVM_MISSING"),
            tls_probe=_StaticProbe(FAKE_CERT_FINGERPRINT),
            http_client_factory=pikvm_http_client_factory(
                env={},
                connection_factory=FakeConnectionFactory(connection),
            ),
        )

    assert SECRET_PASSWORD not in str(excinfo.value) + repr(excinfo.value)
    assert connection.requests == []


def test_real_pikvm_client_error_payloads_stay_redacted() -> None:
    connection = FakeConnection(routes=PIKVM_ROUTES, status=401)
    transport = _live_transport(connection)

    with pytest.raises(Exception) as excinfo:
        transport.get_health()

    text = json.dumps(
        {"error": str(excinfo.value), "repr": repr(excinfo.value)}
    )
    assert SECRET_PASSWORD not in text
    assert "X-KVMD-Passwd" not in text
