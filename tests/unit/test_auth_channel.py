"""Unit coverage for selectable auth-channel resolution and config wiring."""

from __future__ import annotations

import json

import pytest

from agentickvm.config import config_from_mapping, load_config
from agentickvm.config.validation import ConfigValidationError
from agentickvm.control_plane import (
    DEFAULT_AUTH_CHANNEL,
    AuthChannel,
    AuthChannelError,
    LOCAL_TERMINAL_WARNING,
    RECOMMENDED_AUTH_CHANNEL,
    resolve_auth_channel,
)

MOCK_CONFIG = {
    "version": "0.1",
    "providers": [{"id": "mock", "type": "mock", "enabled": True}],
    "targets": [
        {
            "id": "mock-host",
            "provider": "mock",
            "enabled": True,
            "allowed_modes": ["Observe", "Supervised"],
        }
    ],
    "default_policy": {"mode": "Supervised"},
}


def _config_with(**overrides):
    raw = dict(MOCK_CONFIG)
    raw.update(overrides)
    return config_from_mapping(raw)


def test_default_and_recommended_channel_is_mobile_signed() -> None:
    assert DEFAULT_AUTH_CHANNEL == AuthChannel.MOBILE_SIGNED
    assert RECOMMENDED_AUTH_CHANNEL == AuthChannel.MOBILE_SIGNED


def test_resolve_none_yields_recommended_default_without_warning() -> None:
    selection = resolve_auth_channel(None)

    assert selection.channel == AuthChannel.MOBILE_SIGNED
    assert selection.is_default is True
    assert selection.recommended is True
    assert selection.warning is None
    assert selection.authority == "Agentic Control Tower"


def test_resolve_local_terminal_is_opt_out_with_warning() -> None:
    selection = resolve_auth_channel("local_terminal")

    assert selection.channel == AuthChannel.LOCAL_TERMINAL
    assert selection.recommended is False
    assert selection.is_default is False
    assert selection.warning == LOCAL_TERMINAL_WARNING
    assert "less secure" in selection.warning


def test_resolve_normalizes_case_and_whitespace() -> None:
    assert resolve_auth_channel("  MOBILE_SIGNED ").channel == AuthChannel.MOBILE_SIGNED
    assert resolve_auth_channel(AuthChannel.LOCAL_TERMINAL).channel == AuthChannel.LOCAL_TERMINAL


def test_resolve_unknown_channel_fails_closed() -> None:
    with pytest.raises(AuthChannelError, match="unknown auth_channel"):
        resolve_auth_channel("sms_otp")


def test_selection_to_dict_is_audit_friendly() -> None:
    payload = resolve_auth_channel("local_terminal").to_dict()

    assert payload == {
        "channel": "local_terminal",
        "is_default": False,
        "recommended": False,
        "authority": "local signed-grant broker",
        "warning": LOCAL_TERMINAL_WARNING,
    }
    # Must be JSON-serializable for audit records.
    json.dumps(payload)


def test_config_defaults_to_mobile_signed() -> None:
    config = _config_with()

    assert config.auth_channel == AuthChannel.MOBILE_SIGNED
    assert config.auth_channel_selection.recommended is True


def test_config_accepts_local_terminal_opt_out() -> None:
    config = _config_with(auth_channel="local_terminal")

    assert config.auth_channel == AuthChannel.LOCAL_TERMINAL
    assert config.auth_channel_selection.warning == LOCAL_TERMINAL_WARNING


def test_config_accepts_auth_channel_under_default_policy() -> None:
    config = _config_with(default_policy={"mode": "Supervised", "auth_channel": "local_terminal"})

    assert config.auth_channel == AuthChannel.LOCAL_TERMINAL


def test_config_rejects_unknown_auth_channel() -> None:
    with pytest.raises(ConfigValidationError, match="unknown auth_channel"):
        _config_with(auth_channel="carrier_pigeon")


def test_builtin_default_config_is_mobile_signed() -> None:
    # The built-in safe default (no file) must stay on the recommended channel.
    config = load_config(None)

    assert config.auth_channel == AuthChannel.MOBILE_SIGNED
