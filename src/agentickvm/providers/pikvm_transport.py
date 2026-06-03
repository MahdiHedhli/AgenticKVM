"""PiKVM observe transport boundary.

This module intentionally implements only fake transport behavior. It contains
no live network transport, credential resolution, input, power mutation, media,
boot mutation, storage, network, or BMC credential behavior.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from agentickvm.providers.errors import (
    ProviderAuthenticationRequiredError,
    ProviderDisabledError,
    ProviderMutationBlockedError,
    ProviderProtocolError,
    ProviderResponseValidationError,
    ProviderTimeoutError,
)
from agentickvm.providers.transport_policy import TransportSecurityPolicy
from agentickvm.providers.transports import (
    FakeTransport,
    TransportError,
    TransportMethodNotAllowedError,
    TransportRouteNotFoundError,
)

PIKVM_HEALTH_PATH = "/api/health"
PIKVM_SCREEN_STATE_PATH = "/api/screen-state"
PIKVM_SCREENSHOT_METADATA_PATH = "/api/screenshot-metadata"
PIKVM_POWER_STATE_PATH = "/api/power-state"
PIKVM_BOOT_STATUS_PATH = "/api/boot"
PIKVM_HARDWARE_INVENTORY_PATH = "/api/inventory"
PIKVM_EVENT_LOGS_PATH = "/api/events"

_SECRET_KEY_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "credential",
    "cookie",
    "bearer",
    "private_key",
)
_TARGET_SENSITIVE_KEYS = (
    "hostname",
    "host",
    "ip",
    "address",
    "target",
    "url",
)


@runtime_checkable
class PiKVMObserveTransport(Protocol):
    """Observe-only transport contract for PiKVM providers."""

    policy: TransportSecurityPolicy

    def get_health(self) -> Mapping[str, Any]:
        """Return provider health/status metadata."""

    def get_screen_state(self) -> Mapping[str, Any]:
        """Return sanitized screen state or metadata."""

    def get_screenshot_metadata(self) -> Mapping[str, Any]:
        """Return sanitized screenshot artifact metadata, never raw bytes."""

    def get_power_state(self) -> Mapping[str, Any]:
        """Return safe power-state observation."""

    def get_boot_status(self) -> Mapping[str, Any]:
        """Return safe boot-status observation."""


class PiKVMLiveObserveTransportUnavailable:
    """Fail-closed placeholder for future live transport.

    Construction and method calls do not create sockets or resolve credentials.
    """

    policy = TransportSecurityPolicy()

    def __init__(self) -> None:
        raise ProviderDisabledError("PiKVM live observe transport is not implemented")


class FakePiKVMObserveTransport:
    """PiKVM observe transport backed by deterministic fake routes only."""

    def __init__(
        self,
        *,
        transport: FakeTransport,
        policy: TransportSecurityPolicy | None = None,
    ) -> None:
        self.transport = transport
        self.policy = policy or TransportSecurityPolicy()

    def get_health(self) -> Mapping[str, Any]:
        """Return fake health/status metadata."""

        return self._get_mapping(
            PIKVM_HEALTH_PATH,
            required=("health", "fixture"),
        )

    def get_screen_state(self) -> Mapping[str, Any]:
        """Return fake screen metadata."""

        return self._get_mapping(
            PIKVM_SCREEN_STATE_PATH,
            required=("kind", "sensitive", "source"),
        )

    def get_screenshot_metadata(self) -> Mapping[str, Any]:
        """Return fake screenshot metadata without raw screenshot bytes."""

        payload = self._get_mapping(
            PIKVM_SCREENSHOT_METADATA_PATH,
            required=("artifact", "sensitive", "raw_bytes_included"),
        )
        if payload.get("raw_bytes_included") is True:
            raise ProviderResponseValidationError(
                "PiKVM screenshot fixture must not include raw bytes"
            )
        return payload

    def get_power_state(self) -> Mapping[str, Any]:
        """Return fake power-state metadata."""

        return self._get_mapping(PIKVM_POWER_STATE_PATH, required=("power_state",))

    def get_boot_status(self) -> Mapping[str, Any]:
        """Return fake boot-status metadata."""

        return self._get_mapping(PIKVM_BOOT_STATUS_PATH, required=("boot_status",))

    def get_hardware_inventory(self) -> Mapping[str, Any]:
        """Return fake inventory metadata for existing fixture conformance."""

        return self._get_mapping(PIKVM_HARDWARE_INVENTORY_PATH, required=("provider",))

    def get_event_logs(self) -> Mapping[str, Any]:
        """Return fake event-log metadata for existing fixture conformance."""

        return self._get_mapping(PIKVM_EVENT_LOGS_PATH, required=("events",))

    def _get_mapping(
        self,
        path: str,
        *,
        required: tuple[str, ...],
    ) -> Mapping[str, Any]:
        try:
            payload = dict(
                self.transport.request(
                    "GET",
                    path,
                    timeout_seconds=self.policy.read_timeout_seconds,
                ).json()
            )
        except TransportMethodNotAllowedError as exc:
            raise ProviderMutationBlockedError(
                "PiKVM fake observe transport rejected mutating method"
            ) from exc
        except TransportRouteNotFoundError as exc:
            raise ProviderResponseValidationError(
                f"PiKVM fake fixture route missing: {path}"
            ) from exc
        except TransportError as exc:
            raise ProviderProtocolError("PiKVM fake transport error") from exc

        _raise_fixture_error(payload)
        _validate_required(payload, required)
        return MappingProxyType(dict(redact_pikvm_observe_payload(payload)))


def _raise_fixture_error(payload: Mapping[str, Any]) -> None:
    error = payload.get("error")
    if not isinstance(error, Mapping):
        return
    code = str(error.get("code", "unknown"))
    if code == "auth_required":
        raise ProviderAuthenticationRequiredError("PiKVM authentication required")
    if code == "timeout":
        raise ProviderTimeoutError("PiKVM observe request timed out")
    raise ProviderProtocolError("PiKVM fixture returned provider error")


def _validate_required(payload: Mapping[str, Any], required: tuple[str, ...]) -> None:
    missing = [key for key in required if key not in payload]
    if missing:
        raise ProviderResponseValidationError(
            f"PiKVM fixture response missing required fields: {', '.join(missing)}"
        )


def redact_pikvm_observe_payload(value: Any) -> Any:
    """Return a PiKVM-safe observe payload for results and audit metadata."""

    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in _SECRET_KEY_FRAGMENTS):
                redacted[str(key)] = "[REDACTED]"
            elif lowered != "raw_bytes_included" and (
                "raw_bytes" in lowered or lowered in {"bytes", "image_bytes"}
            ):
                redacted[str(key)] = "[REDACTED]"
            elif any(fragment in lowered for fragment in _TARGET_SENSITIVE_KEYS):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_pikvm_observe_payload(child)
        return redacted
    if isinstance(value, (list, tuple)):
        return [redact_pikvm_observe_payload(item) for item in value]
    if isinstance(value, bytes):
        return "[REDACTED-BYTES]"
    return value


__all__ = [
    "FakePiKVMObserveTransport",
    "PIKVM_BOOT_STATUS_PATH",
    "PIKVM_EVENT_LOGS_PATH",
    "PIKVM_HARDWARE_INVENTORY_PATH",
    "PIKVM_HEALTH_PATH",
    "PIKVM_POWER_STATE_PATH",
    "PIKVM_SCREENSHOT_METADATA_PATH",
    "PIKVM_SCREEN_STATE_PATH",
    "PiKVMLiveObserveTransportUnavailable",
    "PiKVMObserveTransport",
    "redact_pikvm_observe_payload",
]
