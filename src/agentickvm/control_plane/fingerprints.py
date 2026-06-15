"""Stable fingerprints for approval-bound action parameters."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


class FingerprintError(ValueError):
    """Raised when values cannot be safely fingerprinted."""


def canonical_json(value: Any) -> str:
    """Return stable JSON for a JSON-safe value."""

    return json.dumps(
        _normalize(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def fingerprint_parameters(parameters: Mapping[str, Any]) -> str:
    """Return a SHA-256 fingerprint for approval-bound parameters."""

    payload = canonical_json(dict(parameters))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, bytes | bytearray | memoryview):
        raise FingerprintError("raw bytes cannot be fingerprinted for approval payloads")
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise FingerprintError("approval parameter keys must be strings")
            normalized[key] = _normalize(item)
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_normalize(item) for item in value]
    raise FingerprintError(f"unsupported approval parameter value: {type(value).__name__}")
