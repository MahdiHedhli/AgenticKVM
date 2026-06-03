import json
import re
from pathlib import Path
from typing import Any

import pytest

from agentickvm.providers.errors import (
    ProviderAuthenticationRequiredError,
    ProviderResponseValidationError,
    ProviderTimeoutError,
)
from agentickvm.providers.pikvm_transport import (
    FakePiKVMObserveTransport,
    PIKVM_HEALTH_PATH,
    PIKVM_POWER_STATE_PATH,
    PIKVM_SCREENSHOT_METADATA_PATH,
    PIKVM_SCREEN_STATE_PATH,
)
from agentickvm.providers.transports import FakeTransport

ROOT = Path(__file__).resolve().parents[1]
PIKVM_FIXTURE_DIR = ROOT / "fixtures" / "providers" / "pikvm"

SECRET_KEY_FRAGMENTS = (
    "password",
    "token",
    "api_key",
    "secret",
    "private_key",
    "bearer",
    "session_cookie",
)
IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((PIKVM_FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _all_fixture_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            values.append(str(key))
            values.extend(_all_fixture_values(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_all_fixture_values(child))
    elif isinstance(value, str):
        values.append(value)
    return values


def _fixture_keys(value: Any) -> list[str]:
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_fixture_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_fixture_keys(child))
    return keys


def test_valid_pikvm_observe_fixtures_parse_through_fake_transport() -> None:
    fake = FakePiKVMObserveTransport(
        transport=FakeTransport(
            {
                ("GET", PIKVM_HEALTH_PATH): _fixture("health.json"),
                ("GET", PIKVM_SCREEN_STATE_PATH): _fixture("screen-state.json"),
                ("GET", PIKVM_SCREENSHOT_METADATA_PATH): _fixture(
                    "screenshot-metadata.json"
                ),
                ("GET", PIKVM_POWER_STATE_PATH): _fixture("power-state.json"),
            }
        )
    )

    assert fake.get_health()["health"] == "ok"
    assert fake.get_screen_state()["source"] == "synthetic-fixture"
    assert fake.get_power_state()["power_state"] == "on"
    screenshot = fake.get_screenshot_metadata()
    assert screenshot["artifact"]["target_id"] == "[REDACTED]"
    assert screenshot["raw_bytes_included"] is False


def test_unexpected_pikvm_fixture_shape_fails_closed() -> None:
    fake = FakePiKVMObserveTransport(
        transport=FakeTransport(
            {("GET", PIKVM_HEALTH_PATH): _fixture("error-unexpected-shape.json")}
        )
    )

    with pytest.raises(ProviderResponseValidationError):
        fake.get_health()


def test_auth_required_fixture_maps_to_auth_required_error() -> None:
    fake = FakePiKVMObserveTransport(
        transport=FakeTransport(
            {("GET", PIKVM_HEALTH_PATH): _fixture("error-auth-required.json")}
        )
    )

    with pytest.raises(ProviderAuthenticationRequiredError) as exc:
        fake.get_health()

    assert exc.value.info.code == "provider_authentication_required"
    assert "credential" not in exc.value.public_message.lower()


def test_timeout_fixture_maps_to_retryable_timeout_error() -> None:
    fake = FakePiKVMObserveTransport(
        transport=FakeTransport(
            {("GET", PIKVM_HEALTH_PATH): _fixture("error-timeout.json")}
        )
    )

    with pytest.raises(ProviderTimeoutError) as exc:
        fake.get_health()

    assert exc.value.info.code == "provider_timeout"
    assert exc.value.info.retryable is True


def test_screenshot_fixture_is_metadata_only_and_redacted() -> None:
    fixture = _fixture("screenshot-metadata.json")
    fake = FakePiKVMObserveTransport(
        transport=FakeTransport({("GET", PIKVM_SCREENSHOT_METADATA_PATH): fixture})
    )

    result = fake.get_screenshot_metadata()

    assert fixture["raw_bytes_included"] is False
    assert "raw_image" not in repr(fixture)
    assert result["artifact"]["target_id"] == "[REDACTED]"
    assert result["artifact"]["storage"] == "metadata-only"


def test_pikvm_fixtures_contain_no_secret_like_keys_or_values() -> None:
    for fixture_path in PIKVM_FIXTURE_DIR.glob("*.json"):
        fixture = _fixture(fixture_path.name)
        keys = [key.lower() for key in _fixture_keys(fixture)]
        values = [value.lower() for value in _all_fixture_values(fixture)]

        assert not any(
            fragment in key
            for key in keys
            for fragment in SECRET_KEY_FRAGMENTS
        ), fixture_path.name
        assert not any("keychain://" in value for value in values)
        assert not any("vault://" in value for value in values)
        assert not any("env://" in value for value in values)
        assert not any("bearer " in value for value in values)
        assert not any("password=" in value for value in values)
        assert not any("token=" in value for value in values)


def test_pikvm_fixtures_use_documentation_safe_hosts_only() -> None:
    for fixture_path in PIKVM_FIXTURE_DIR.glob("*.json"):
        fixture_text = fixture_path.read_text(encoding="utf-8")
        assert "192.168." not in fixture_text
        assert "10." not in fixture_text
        assert "172.16." not in fixture_text
        assert not IPV4_PATTERN.search(fixture_text), fixture_path.name
        assert ".local" not in fixture_text
