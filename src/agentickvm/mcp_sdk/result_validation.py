"""Lightweight host result validation.

This module intentionally avoids external schema dependencies. It validates the
dependency-free host compatibility result shape before future MCP SDK/server
adapters are allowed to treat a payload as host-safe.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from agentickvm.mcp_sdk.approval_models import HostApprovalResultStatus
from agentickvm.mcp_sdk.host_models import HOST_RESULT_STATUSES, HostResultStatus

APPROVAL_RESULT_STATUSES = tuple(status.value for status in HostApprovalResultStatus)
HOST_COMPATIBILITY_STATUSES = HOST_RESULT_STATUSES + APPROVAL_RESULT_STATUSES

_SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "token",
    "api_key",
    "private_key",
    "credential",
    "bearer",
    "session_cookie",
)


class HostResultValidationError(ValueError):
    """Raised when a host result payload is not safe or schema-compatible."""


def validate_host_result(payload: Mapping[str, Any]) -> None:
    """Validate a host compatibility result payload.

    The validator is intentionally minimal and dependency-free. It does not
    replace formal JSON Schema work, but it fails closed on unsafe or unstable
    shapes that a future live MCP server must not emit.
    """

    if not isinstance(payload, Mapping):
        raise HostResultValidationError("host result must be an object")
    _assert_json_safe(payload)
    _assert_no_unredacted_sensitive_keys(payload)

    status = payload.get("status")
    if not isinstance(status, str) or status not in HOST_COMPATIBILITY_STATUSES:
        raise HostResultValidationError("host result status is unknown")

    if status in HOST_RESULT_STATUSES:
        _validate_tool_result(payload, HostResultStatus(status))
    elif status in APPROVAL_RESULT_STATUSES:
        _validate_approval_result(payload)


def _validate_tool_result(
    payload: Mapping[str, Any],
    status: HostResultStatus,
) -> None:
    for field in ("status", "reason"):
        if not isinstance(payload.get(field), str):
            raise HostResultValidationError(f"host result {field} is required")

    if status in {
        HostResultStatus.OK,
        HostResultStatus.DENIED,
        HostResultStatus.APPROVAL_REQUIRED,
        HostResultStatus.PROVIDER_ERROR,
    }:
        for field in ("tool_name", "target", "provider"):
            if not isinstance(payload.get(field), str):
                raise HostResultValidationError(f"host result {field} is required")
    if status == HostResultStatus.APPROVAL_REQUIRED:
        approval = payload.get("approval_request")
        if not isinstance(approval, Mapping):
            raise HostResultValidationError("approval_required result needs approval_request")
        for field in (
            "id",
            "session_id",
            "target",
            "provider",
            "capability",
            "params_fingerprint",
        ):
            if not isinstance(approval.get(field), str) or not approval[field]:
                raise HostResultValidationError(
                    f"approval_required approval_request {field} is required"
                )
    if status == HostResultStatus.PROVIDER_ERROR:
        provider_result = _provider_result(payload)
        if provider_result is None:
            raise HostResultValidationError("provider_error needs provider_result")
        if not isinstance(provider_result.get("error_code"), str):
            raise HostResultValidationError("provider_error needs error_code")


def _validate_approval_result(payload: Mapping[str, Any]) -> None:
    for field in ("status", "request_id", "reason"):
        if not isinstance(payload.get(field), str):
            raise HostResultValidationError(f"approval result {field} is required")


def _provider_result(payload: Mapping[str, Any]) -> Mapping[str, Any] | None:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        return None
    provider_result = data.get("provider_result")
    return provider_result if isinstance(provider_result, Mapping) else None


def _assert_json_safe(payload: Mapping[str, Any]) -> None:
    try:
        json.dumps(payload, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise HostResultValidationError("host result must be JSON-safe") from exc
    _assert_no_raw_bytes(payload)


def _assert_no_raw_bytes(value: Any) -> None:
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise HostResultValidationError("host result must not include raw bytes")
    if isinstance(value, Mapping):
        for child in value.values():
            _assert_no_raw_bytes(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_no_raw_bytes(child)


def _assert_no_unredacted_sensitive_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS):
                if child not in (None, "", "[REDACTED]"):
                    raise HostResultValidationError(
                        f"host result contains unredacted sensitive key {key}"
                    )
            _assert_no_unredacted_sensitive_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _assert_no_unredacted_sensitive_keys(child)


__all__ = [
    "APPROVAL_RESULT_STATUSES",
    "HOST_COMPATIBILITY_STATUSES",
    "HostResultValidationError",
    "validate_host_result",
]
