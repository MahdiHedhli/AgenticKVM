"""PiKVM observe transport boundary.

This module intentionally implements only fake transport behavior. It contains
no live network transport, credential resolution, input, power mutation, media,
boot mutation, storage, network, or BMC credential behavior.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Callable, Protocol, runtime_checkable

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
from agentickvm.redaction import redact_value as redact_agentickvm_value

PIKVM_HEALTH_PATH = "/api/health"
PIKVM_SCREEN_STATE_PATH = "/api/screen-state"
PIKVM_SCREENSHOT_METADATA_PATH = "/api/screenshot-metadata"
PIKVM_POWER_STATE_PATH = "/api/power-state"
PIKVM_BOOT_STATUS_PATH = "/api/boot"
PIKVM_HARDWARE_INVENTORY_PATH = "/api/inventory"
PIKVM_EVENT_LOGS_PATH = "/api/events"
PIKVM_DEVICE_INFO_PATH = "/api/device-info"

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

    def get_device_info(self) -> Mapping[str, Any]:
        """Return safe device information."""


class PiKVMLiveObserveTransportUnavailable:
    """Fail-closed placeholder for future live transport.

    Construction and method calls do not create sockets or resolve credentials.
    """

    policy = TransportSecurityPolicy()

    def __init__(self) -> None:
        raise ProviderDisabledError("PiKVM live observe transport is not implemented")


@dataclass(frozen=True)
class PiKVMTargetConfig:
    """Live PiKVM target connection metadata without credentials."""

    base_url: str
    cert_fingerprint: str | None = None
    verify_ssl: bool = True
    port: int = 443
    connect_timeout_seconds: float = 2.0
    read_timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ProviderProtocolError("PiKVM live transport requires https base_url")
        if self.port <= 0:
            raise ProviderProtocolError("PiKVM port must be positive")
        if not self.verify_ssl and not self.cert_fingerprint:
            raise ProviderProtocolError(
                "verify_ssl=false is allowed only with cert_fingerprint pinning"
            )

    @property
    def host(self) -> str:
        """Return host component without credentials or path."""

        without_scheme = self.base_url.removeprefix("https://")
        return without_scheme.split("/", 1)[0].split(":", 1)[0]


@dataclass(frozen=True)
class PiKVMCredentialRef:
    """Credential reference; raw credential resolution is out of scope."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.value:
            raise ProviderAuthenticationRequiredError("PiKVM credential_ref is required")
        if any(fragment in self.value.lower() for fragment in ("password=", "token=", "secret=")):
            raise ProviderAuthenticationRequiredError(
                "PiKVM transport accepts credential references only, not raw secrets"
            )

    def safe_label(self) -> str:
        """Return a non-secret label for result/debug shapes."""

        return "[CREDENTIAL_REF]"


@dataclass(frozen=True)
class PiKVMPinnedTrust:
    """Pinned certificate trust root for a PiKVM target."""

    sha256_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "sha256_fingerprint", normalize_cert_fingerprint(self.sha256_fingerprint))


class PiKVMTLSProbe(Protocol):
    """Unauthenticated TLS certificate probe used before credentials exist."""

    def certificate_der_sha256(
        self,
        *,
        host: str,
        port: int,
        timeout_seconds: float,
    ) -> str:
        """Return the peer certificate SHA-256 fingerprint."""


class PiKVMAuthenticatedHTTPClient(Protocol):
    """Authenticated observe-only HTTP client created after preflight passes."""

    trust: PiKVMPinnedTrust | None

    def get_json(self, path: str, *, timeout_seconds: float) -> Mapping[str, Any]:
        """Return a JSON mapping for an observe-only GET path."""


PiKVMHTTPClientFactory = Callable[
    [PiKVMTargetConfig, PiKVMCredentialRef, PiKVMPinnedTrust | None],
    PiKVMAuthenticatedHTTPClient,
]


class PiKVMFingerprintMismatchError(ProviderProtocolError):
    """Raised when the unauthenticated TLS preflight sees the wrong cert."""


class LivePiKVMObserveTransport:
    """Observe-only PiKVM transport built only after TLS pinning preflight."""

    policy = TransportSecurityPolicy()

    def __init__(
        self,
        *,
        config: PiKVMTargetConfig,
        credential_ref: PiKVMCredentialRef,
        tls_probe: PiKVMTLSProbe,
        http_client_factory: PiKVMHTTPClientFactory,
        policy: TransportSecurityPolicy | None = None,
    ) -> None:
        self.config = config
        self.credential_ref = credential_ref
        self.policy = policy or TransportSecurityPolicy(
            read_timeout_seconds=config.read_timeout_seconds,
            connect_timeout_seconds=config.connect_timeout_seconds,
            tls_verify=config.verify_ssl,
            allow_insecure_tls=not config.verify_ssl and bool(config.cert_fingerprint),
        )
        trust = self._preflight_pin(tls_probe)
        self.http = http_client_factory(config, credential_ref, trust)

    def get_health(self) -> Mapping[str, Any]:
        return self._get_mapping(PIKVM_HEALTH_PATH, required=("health",))

    def get_screen_state(self) -> Mapping[str, Any]:
        return self._get_mapping(PIKVM_SCREEN_STATE_PATH, required=("kind",))

    def get_screenshot_metadata(self) -> Mapping[str, Any]:
        payload = self._get_mapping(
            PIKVM_SCREENSHOT_METADATA_PATH,
            required=("artifact", "raw_bytes_included"),
        )
        if payload.get("raw_bytes_included") is True:
            raise ProviderResponseValidationError("PiKVM live screenshot metadata included raw bytes")
        return payload

    def get_power_state(self) -> Mapping[str, Any]:
        return self._get_mapping(PIKVM_POWER_STATE_PATH, required=("power_state",))

    def get_boot_status(self) -> Mapping[str, Any]:
        return self._get_mapping(PIKVM_BOOT_STATUS_PATH, required=("boot_status",))

    def get_hardware_inventory(self) -> Mapping[str, Any]:
        return self.get_device_info()

    def get_device_info(self) -> Mapping[str, Any]:
        return self._get_mapping(PIKVM_DEVICE_INFO_PATH, required=("provider",))

    def _preflight_pin(self, tls_probe: PiKVMTLSProbe) -> PiKVMPinnedTrust | None:
        if not self.config.cert_fingerprint:
            return None
        expected = normalize_cert_fingerprint(self.config.cert_fingerprint)
        observed = normalize_cert_fingerprint(
            tls_probe.certificate_der_sha256(
                host=self.config.host,
                port=self.config.port,
                timeout_seconds=self.config.connect_timeout_seconds,
            )
        )
        if observed != expected:
            raise PiKVMFingerprintMismatchError(
                "PiKVM certificate fingerprint mismatch; credentials were not sent"
            )
        return PiKVMPinnedTrust(expected)

    def _get_mapping(
        self,
        path: str,
        *,
        required: tuple[str, ...],
    ) -> Mapping[str, Any]:
        try:
            payload = dict(
                self.http.get_json(
                    path,
                    timeout_seconds=self.policy.read_timeout_seconds,
                )
            )
        except TransportError as exc:
            raise ProviderProtocolError("PiKVM live observe transport error") from exc
        _validate_required(payload, required)
        return MappingProxyType(dict(redact_pikvm_observe_payload(payload)))


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

    def get_device_info(self) -> Mapping[str, Any]:
        """Return fake device metadata."""

        return self.get_hardware_inventory()

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


def redact_pikvm_observe_payload(value: Any, *, full_capture: bool = False) -> Any:
    """Return a PiKVM-safe observe payload for results and audit metadata."""

    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, child in value.items():
            lowered = str(key).lower()
            if lowered != "raw_bytes_included" and (
                "raw_bytes" in lowered or lowered in {"bytes", "image_bytes"}
            ):
                redacted[str(key)] = "[REDACTED]"
            elif any(fragment in lowered for fragment in _TARGET_SENSITIVE_KEYS):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_pikvm_observe_payload(
                    child,
                    full_capture=full_capture,
                )
        return redact_agentickvm_value(redacted, full_capture=full_capture).value
    return redact_agentickvm_value(value, full_capture=full_capture).value


def normalize_cert_fingerprint(value: str) -> str:
    """Normalize a SHA-256 cert fingerprint for comparison."""

    compact = re.sub(r"[^0-9A-Fa-f]", "", value).lower()
    if len(compact) != 64:
        raise ProviderProtocolError("PiKVM cert_fingerprint must be a SHA-256 fingerprint")
    return ":".join(compact[index : index + 2] for index in range(0, 64, 2))


def sha256_fingerprint_for_der(cert_der: bytes) -> str:
    """Return normalized SHA-256 fingerprint for DER certificate bytes."""

    return normalize_cert_fingerprint(hashlib.sha256(cert_der).hexdigest())


__all__ = [
    "FakePiKVMObserveTransport",
    "LivePiKVMObserveTransport",
    "PIKVM_BOOT_STATUS_PATH",
    "PIKVM_DEVICE_INFO_PATH",
    "PIKVM_EVENT_LOGS_PATH",
    "PIKVM_HARDWARE_INVENTORY_PATH",
    "PIKVM_HEALTH_PATH",
    "PIKVM_POWER_STATE_PATH",
    "PIKVM_SCREENSHOT_METADATA_PATH",
    "PIKVM_SCREEN_STATE_PATH",
    "PiKVMLiveObserveTransportUnavailable",
    "PiKVMCredentialRef",
    "PiKVMFingerprintMismatchError",
    "PiKVMPinnedTrust",
    "PiKVMTargetConfig",
    "PiKVMObserveTransport",
    "normalize_cert_fingerprint",
    "redact_pikvm_observe_payload",
    "sha256_fingerprint_for_der",
]
