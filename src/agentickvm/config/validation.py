"""Configuration validation helpers."""

from __future__ import annotations

from typing import Any, Mapping

SUSPICIOUS_CONFIG_KEY_FRAGMENTS = frozenset(
    {
        "password",
        "token",
        "api_key",
        "secret",
        "private_key",
        "credential",
    }
)

DYNAMIC_IMPORT_CONFIG_KEYS = frozenset(
    {
        "class",
        "factory",
        "import",
        "module",
        "object",
    }
)


class ConfigValidationError(ValueError):
    """Raised when configuration fails closed."""


def reject_unsafe_config_keys(value: Any, *, path: str = "config") -> None:
    """Reject secret-like and dynamic-import-like config keys."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(fragment in lowered for fragment in SUSPICIOUS_CONFIG_KEY_FRAGMENTS):
                raise ConfigValidationError(f"Secret-like config key rejected: {path}.{key_text}")
            if lowered in DYNAMIC_IMPORT_CONFIG_KEYS:
                raise ConfigValidationError(
                    f"Dynamic import config key rejected: {path}.{key_text}"
                )
            reject_unsafe_config_keys(child, path=f"{path}.{key_text}")
    elif isinstance(value, (list, tuple, set, frozenset)):
        for index, child in enumerate(value):
            reject_unsafe_config_keys(child, path=f"{path}[{index}]")


__all__ = [
    "ConfigValidationError",
    "DYNAMIC_IMPORT_CONFIG_KEYS",
    "SUSPICIOUS_CONFIG_KEY_FRAGMENTS",
    "reject_unsafe_config_keys",
]
