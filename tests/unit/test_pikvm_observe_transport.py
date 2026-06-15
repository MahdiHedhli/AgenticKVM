import inspect

import pytest

from agentickvm.providers import pikvm_transport as transport_module
from agentickvm.providers.errors import (
    ProviderAuthenticationRequiredError,
    ProviderDisabledError,
    ProviderMutationBlockedError,
    ProviderResponseValidationError,
    ProviderTimeoutError,
)
from agentickvm.providers.pikvm import default_pikvm_fake_transport
from agentickvm.providers.pikvm_transport import (
    FakePiKVMObserveTransport,
    LivePiKVMObserveTransport,
    PIKVM_HEALTH_PATH,
    PIKVM_DEVICE_INFO_PATH,
    PIKVM_POWER_STATE_PATH,
    PIKVM_SCREENSHOT_METADATA_PATH,
    PIKVM_SCREEN_STATE_PATH,
    PiKVMCredentialRef,
    PiKVMFingerprintMismatchError,
    PiKVMPinnedTrust,
    PiKVMTargetConfig,
    PiKVMLiveObserveTransportUnavailable,
    normalize_cert_fingerprint,
    redact_pikvm_observe_payload,
)
from agentickvm.providers.transports import FakeTransport


GOOD_FINGERPRINT = "aa" * 32
BAD_FINGERPRINT = "bb" * 32


class MockTLSProbe:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint
        self.calls = []

    def certificate_der_sha256(self, *, host: str, port: int, timeout_seconds: float) -> str:
        self.calls.append({"host": host, "port": port, "timeout_seconds": timeout_seconds})
        return self.fingerprint


class MockAuthenticatedHTTPClient:
    def __init__(self, *, trust: PiKVMPinnedTrust | None) -> None:
        self.trust = trust
        self.calls = []
        self.routes = {
            PIKVM_HEALTH_PATH: {"health": "ok"},
            PIKVM_SCREEN_STATE_PATH: {"kind": "mjpeg_snapshot", "sensitive": True},
            PIKVM_SCREENSHOT_METADATA_PATH: {
                "artifact": {"kind": "screenshot", "storage": "metadata-only"},
                "raw_bytes_included": False,
            },
            PIKVM_POWER_STATE_PATH: {"power_state": "on"},
            "/api/boot": {"boot_status": "os_running"},
            PIKVM_DEVICE_INFO_PATH: {"provider": "pikvm", "model": "mock"},
        }

    def get_json(self, path: str, *, timeout_seconds: float):
        self.calls.append({"path": path, "timeout_seconds": timeout_seconds})
        return self.routes[path]


class RecordingFactory:
    def __init__(self) -> None:
        self.credential_received = None
        self.trust_received = None
        self.client = None

    def __call__(self, config, credential_ref, trust):
        self.credential_received = credential_ref
        self.trust_received = trust
        self.client = MockAuthenticatedHTTPClient(trust=trust)
        return self.client


def test_fake_pikvm_observe_transport_returns_fixture_observations() -> None:
    fake = FakePiKVMObserveTransport(transport=default_pikvm_fake_transport())

    health = fake.get_health()
    screen = fake.get_screen_state()
    screenshot = fake.get_screenshot_metadata()
    power = fake.get_power_state()

    assert health["health"] == "ok"
    assert screen["content"] == "PiKVM fixture screen"
    assert screenshot["artifact"]["target_id"] == "[REDACTED]"
    assert screenshot["raw_bytes_included"] is False
    assert power["power_state"] == "on"
    assert [call.method for call in fake.transport.calls] == ["GET", "GET", "GET", "GET"]


def test_fake_pikvm_transport_rejects_unknown_fixture_routes() -> None:
    fake = FakePiKVMObserveTransport(
        transport=FakeTransport({("GET", PIKVM_HEALTH_PATH): {"health": "ok", "fixture": True}})
    )

    with pytest.raises(ProviderResponseValidationError):
        fake.get_screen_state()


def test_fake_pikvm_transport_rejects_unexpected_shape() -> None:
    fake = FakePiKVMObserveTransport(
        transport=FakeTransport(
            {("GET", PIKVM_SCREEN_STATE_PATH): {"kind": "text_snapshot"}}
        )
    )

    with pytest.raises(ProviderResponseValidationError):
        fake.get_screen_state()


def test_fake_pikvm_transport_maps_auth_and_timeout_fixture_errors() -> None:
    auth = FakePiKVMObserveTransport(
        transport=FakeTransport(
            {
                (
                    "GET",
                    PIKVM_HEALTH_PATH,
                ): {"error": {"code": "auth_required", "message": "credentials required"}}
            }
        )
    )
    timeout = FakePiKVMObserveTransport(
        transport=FakeTransport(
            {("GET", PIKVM_HEALTH_PATH): {"error": {"code": "timeout", "message": "timed out"}}}
        )
    )

    with pytest.raises(ProviderAuthenticationRequiredError):
        auth.get_health()
    with pytest.raises(ProviderTimeoutError):
        timeout.get_health()


def test_fake_pikvm_transport_blocks_mutating_methods() -> None:
    fake = FakePiKVMObserveTransport(
        transport=FakeTransport(
            {("POST", PIKVM_HEALTH_PATH): {"ok": True}},
            allowed_methods=frozenset({"POST"}),
        )
    )

    with pytest.raises(ProviderMutationBlockedError):
        fake.get_health()


def test_live_pikvm_transport_unavailable_by_default() -> None:
    with pytest.raises(ProviderDisabledError):
        PiKVMLiveObserveTransportUnavailable()


def test_pikvm_cert_preflight_match_builds_authenticated_client_with_pinned_trust() -> None:
    factory = RecordingFactory()
    transport = LivePiKVMObserveTransport(
        config=PiKVMTargetConfig(
            base_url="https://pikvm.example.invalid",
            cert_fingerprint=GOOD_FINGERPRINT,
            verify_ssl=False,
        ),
        credential_ref=PiKVMCredentialRef("keychain://pikvm/mock"),
        tls_probe=MockTLSProbe(GOOD_FINGERPRINT),
        http_client_factory=factory,
    )

    assert factory.credential_received.safe_label() == "[CREDENTIAL_REF]"
    assert factory.trust_received.sha256_fingerprint == normalize_cert_fingerprint(GOOD_FINGERPRINT)
    assert transport.http.trust == factory.trust_received


def test_pikvm_cert_preflight_mismatch_aborts_before_credentials_are_sent() -> None:
    factory = RecordingFactory()

    with pytest.raises(PiKVMFingerprintMismatchError):
        LivePiKVMObserveTransport(
            config=PiKVMTargetConfig(
                base_url="https://pikvm.example.invalid",
                cert_fingerprint=GOOD_FINGERPRINT,
                verify_ssl=False,
            ),
            credential_ref=PiKVMCredentialRef("keychain://pikvm/mock"),
            tls_probe=MockTLSProbe(BAD_FINGERPRINT),
            http_client_factory=factory,
        )

    assert factory.credential_received is None
    assert factory.client is None


def test_pikvm_verify_ssl_false_without_fingerprint_is_rejected() -> None:
    with pytest.raises(Exception, match="verify_ssl=false"):
        PiKVMTargetConfig(
            base_url="https://pikvm.example.invalid",
            cert_fingerprint=None,
            verify_ssl=False,
        )


def test_live_pikvm_observe_surface_shapes_against_mock_http() -> None:
    factory = RecordingFactory()
    transport = LivePiKVMObserveTransport(
        config=PiKVMTargetConfig(
            base_url="https://pikvm.example.invalid",
            cert_fingerprint=GOOD_FINGERPRINT,
            verify_ssl=False,
        ),
        credential_ref=PiKVMCredentialRef("keychain://pikvm/mock"),
        tls_probe=MockTLSProbe(GOOD_FINGERPRINT),
        http_client_factory=factory,
    )

    assert transport.get_health()["health"] == "ok"
    assert transport.get_screen_state()["kind"] == "mjpeg_snapshot"
    assert transport.get_screenshot_metadata()["raw_bytes_included"] is False
    assert transport.get_power_state()["power_state"] == "on"
    assert transport.get_device_info()["provider"] == "pikvm"
    assert [call["path"] for call in factory.client.calls] == [
        PIKVM_HEALTH_PATH,
        PIKVM_SCREEN_STATE_PATH,
        PIKVM_SCREENSHOT_METADATA_PATH,
        PIKVM_POWER_STATE_PATH,
        PIKVM_DEVICE_INFO_PATH,
    ]


def test_pikvm_credential_ref_is_never_embedded_in_result_shapes() -> None:
    factory = RecordingFactory()
    credential = PiKVMCredentialRef("keychain://pikvm/sensitive-ref")
    transport = LivePiKVMObserveTransport(
        config=PiKVMTargetConfig(
            base_url="https://pikvm.example.invalid",
            cert_fingerprint=GOOD_FINGERPRINT,
            verify_ssl=False,
        ),
        credential_ref=credential,
        tls_probe=MockTLSProbe(GOOD_FINGERPRINT),
        http_client_factory=factory,
    )

    result = {
        "health": transport.get_health(),
        "device": transport.get_device_info(),
        "credential": credential.safe_label(),
    }

    assert "keychain://pikvm/sensitive-ref" not in repr(result)
    assert "[CREDENTIAL_REF]" in repr(result)


def test_pikvm_observe_transport_reads_no_env_secrets(monkeypatch) -> None:
    monkeypatch.setenv("AGENTICKVM_PASSWORD", "must-not-leak-provider-secret")
    fake = FakePiKVMObserveTransport(transport=default_pikvm_fake_transport())

    result = fake.get_health()

    assert "must-not-leak-provider-secret" not in repr(result)


def test_pikvm_transport_module_has_no_live_io_imports() -> None:
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
    ):
        assert item not in source


def test_pikvm_transport_redacts_observe_payload_metadata() -> None:
    redacted = redact_pikvm_observe_payload(
        {
            "credential_ref": "keychain://pikvm/example",
            "target_hostname": "lab-pikvm.local",
            "image_bytes": b"fake",
            "nested": {"session_cookie": "cookie-value"},
        }
    )

    assert redacted["credential_ref"] == "[REDACTED]"
    assert redacted["target_hostname"] == "[REDACTED]"
    assert redacted["image_bytes"] == "[REDACTED]"
    assert redacted["nested"]["session_cookie"] == "[REDACTED]"
