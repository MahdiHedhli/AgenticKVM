"""AgenticKVM-local redaction helpers for HID and observe paths.

This is separate from ACT notification redaction. AgenticKVM uses it for local
provider results, audit records, and PiKVM observe/HID-adjacent data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping


REDACTED = "[REDACTED]"
REDACTED_HID_TEXT = REDACTED

HID_TEXT_KEYS = frozenset(
    {
        "text",
        "typed_text",
        "hid_text",
        "keyboard_text",
        "screen_text",
        "screen_content",
        "content",
    }
)

CREDENTIAL_FIELD_KEYS = frozenset(
    {
        "password",
        "passphrase",
        "pin",
        "otp",
        "totp",
        "mfa",
        "mfa_code",
        "recovery_key",
        "secret",
        "token",
        "api_key",
        "api_token",
        "access_token",
        "refresh_token",
        "auth_token",
        "private_key",
        "credential",
        "credential_ref",
        "bearer",
        "session_cookie",
        "otp_secret",
        "token_example",
    }
)
RAW_ARTIFACT_KEYS = frozenset(
    {
        "raw_bytes",
        "image_bytes",
        "raw_image",
        "screenshot_bytes",
        "bytes",
    }
)
STRUCTURAL_TOKEN_KEYS = frozenset(
    {
        "id",
        "event_hash",
        "previous_hash",
        "last_event_hash",
        "checkpoint_hash",
        "params_fingerprint",
        "fingerprint",
        "cert_fingerprint",
        "sha256_fingerprint",
    }
)

SECRET_ASSIGNMENT_RE = re.compile(
    r"\b(password|passphrase|token|secret|api[_-]?key|private[_-]?key|bearer|"
    r"session[_-]?cookie|mfa|otp|totp|recovery[_ -]?key)\b\s*[:=]\s*\S+",
    re.IGNORECASE,
)
HIGH_ENTROPY_RE = re.compile(
    r"\b(?=[A-Za-z0-9+/=_-]{20,}\b)(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])"
    r"[A-Za-z0-9+/=_-]{20,}\b"
)
HEX_SECRET_RE = re.compile(r"\b[0-9a-fA-F]{32,}\b")
MFA_CODE_RE = re.compile(r"\b(?:mfa|otp|totp|code)\s*[:=]?\s*(\d{6,8})\b", re.IGNORECASE)


class CapturePosture(StrEnum):
    """HID/observe capture posture."""

    DEFAULT_REDACTED = "default_redacted"
    FULL_CAPTURE_REDUCED_PROTECTION = "full_capture_reduced_protection"


@dataclass(frozen=True)
class RedactionResult:
    """Redacted value plus metadata."""

    value: Any
    redacted: bool
    reasons: tuple[str, ...] = ()


def hid_capture_posture(*, full_capture: bool) -> Mapping[str, Any]:
    """Return audit-safe posture metadata."""

    posture = (
        CapturePosture.FULL_CAPTURE_REDUCED_PROTECTION
        if full_capture
        else CapturePosture.DEFAULT_REDACTED
    )
    return MappingProxyType(
        {
            "full_capture": full_capture,
            "posture": posture.value,
            "warning": (
                "full capture reduces HID text protection; credential-class "
                "strings are still stripped"
                if full_capture
                else "HID and screen text are redacted by default"
            ),
        }
    )


def explicit_full_capture_enabled(value: Any) -> bool:
    """Return whether an explicit full-capture opt-in value is enabled."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "full"}
    return False


def is_hid_text_key(key: str) -> bool:
    """Return whether a field is allowed to carry HID or observed screen text."""

    return key.lower() in HID_TEXT_KEYS


def is_credential_field_key(key: str) -> bool:
    """Return whether a field is credential-class by allowlisted exact names."""

    return key.lower() in CREDENTIAL_FIELD_KEYS


def is_structural_token_key(key: str) -> bool:
    """Return whether token-shaped values are structural metadata, not secrets."""

    lowered = key.lower()
    return lowered in STRUCTURAL_TOKEN_KEYS or lowered.endswith(
        ("_id", "_hash", "_fingerprint")
    )


def contains_secret_pattern(value: str) -> bool:
    """Return whether text looks credential-like or token-like."""

    return bool(
        SECRET_ASSIGNMENT_RE.search(value)
        or HIGH_ENTROPY_RE.search(value)
        or HEX_SECRET_RE.search(value)
        or MFA_CODE_RE.search(value)
    )


def redact_hid_text(value: str, *, full_capture: bool = False) -> RedactionResult:
    """Redact HID or observed screen text according to capture posture."""

    if not full_capture:
        return RedactionResult(REDACTED_HID_TEXT, True, ("hid_text_default",))
    redacted = _strip_secret_text(value)
    changed = redacted != value
    return RedactionResult(
        redacted,
        changed,
        ("credential_backstop",) if changed else (),
    )


def redact_value(
    value: Any,
    *,
    key: str = "",
    path: str = "",
    full_capture: bool = False,
) -> RedactionResult:
    """Redact a nested value for AgenticKVM local results and audit."""

    if key.lower() == "redactions" and isinstance(value, list):
        return RedactionResult(list(value), False, ())
    if is_credential_field_key(key) or key.lower() in RAW_ARTIFACT_KEYS:
        return RedactionResult(REDACTED, True, ("credential_field",))
    if is_hid_text_key(key) and isinstance(value, str):
        return redact_hid_text(value, full_capture=full_capture)
    if (
        isinstance(value, str)
        and not is_structural_token_key(key)
        and contains_secret_pattern(value)
    ):
        return RedactionResult(REDACTED, True, ("secret_pattern",))
    if isinstance(value, bytes):
        return RedactionResult("[REDACTED-BYTES]", True, ("bytes",))
    if isinstance(value, Mapping):
        child_full_capture = _mapping_full_capture(value, inherited=full_capture)
        redactions: list[str] = []
        redacted: dict[str, Any] = {}
        for child_key, child_value in value.items():
            child_path = f"{path}.{child_key}" if path else str(child_key)
            child = redact_value(
                child_value,
                key=str(child_key),
                path=child_path,
                full_capture=child_full_capture,
            )
            redacted[str(child_key)] = child.value
            if child.redacted:
                nested_paths = tuple(
                    reason
                    for reason in child.reasons
                    if reason == child_path
                    or reason.startswith(f"{child_path}.")
                    or reason.startswith(f"{child_path}[")
                )
                redactions.extend(nested_paths or (child_path,))
        return RedactionResult(redacted, bool(redactions), tuple(redactions))
    if isinstance(value, list):
        redactions: list[str] = []
        redacted_items = []
        for index, item in enumerate(value):
            child = redact_value(
                item,
                key=key,
                path=f"{path}[{index}]",
                full_capture=full_capture,
            )
            redacted_items.append(child.value)
            if child.redacted:
                child_path = f"{path}[{index}]"
                nested_paths = tuple(
                    reason
                    for reason in child.reasons
                    if reason == child_path
                    or reason.startswith(f"{child_path}.")
                    or reason.startswith(f"{child_path}[")
                )
                redactions.extend(nested_paths or (child_path,))
        return RedactionResult(redacted_items, bool(redactions), tuple(redactions))
    if isinstance(value, tuple):
        child = redact_value(list(value), key=key, path=path, full_capture=full_capture)
        return RedactionResult(tuple(child.value), child.redacted, child.reasons)
    return RedactionResult(value, False, ())


def redact_mapping(
    values: Mapping[str, Any],
    *,
    full_capture: bool | None = None,
) -> tuple[Mapping[str, Any], tuple[str, ...]]:
    """Return a redacted mapping and redacted paths."""

    effective_full_capture = _mapping_full_capture(values, inherited=bool(full_capture))
    redacted: dict[str, Any] = {}
    redactions: list[str] = []
    for key, value in values.items():
        result = redact_value(
            value,
            key=str(key),
            path=str(key),
            full_capture=effective_full_capture,
        )
        redacted[str(key)] = result.value
        if result.redacted:
            key_path = str(key)
            nested_paths = tuple(
                reason
                for reason in result.reasons
                if reason == key_path
                or reason.startswith(f"{key_path}.")
                or reason.startswith(f"{key_path}[")
            )
            redactions.extend(nested_paths or (key_path,))
    return MappingProxyType(redacted), tuple(redactions)


def _mapping_full_capture(values: Mapping[str, Any], *, inherited: bool) -> bool:
    posture = values.get("hid_capture")
    if isinstance(posture, Mapping):
        return explicit_full_capture_enabled(posture.get("full_capture"))
    for key in ("PIKVM_FULL_CAPTURE", "pikvm_full_capture", "full_capture"):
        if key in values:
            return explicit_full_capture_enabled(values[key])
    return inherited


def _strip_secret_text(value: str) -> str:
    redacted = SECRET_ASSIGNMENT_RE.sub(lambda match: f"{match.group(1)}={REDACTED}", value)
    redacted = MFA_CODE_RE.sub(
        lambda match: match.group(0).replace(match.group(1), REDACTED),
        redacted,
    )
    redacted = HIGH_ENTROPY_RE.sub(REDACTED, redacted)
    redacted = HEX_SECRET_RE.sub(REDACTED, redacted)
    return redacted
