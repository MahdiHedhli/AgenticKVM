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
    PIKVM_HEALTH_PATH,
    PIKVM_SCREEN_STATE_PATH,
    PiKVMLiveObserveTransportUnavailable,
    redact_pikvm_observe_payload,
)
from agentickvm.providers.transports import FakeTransport


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
