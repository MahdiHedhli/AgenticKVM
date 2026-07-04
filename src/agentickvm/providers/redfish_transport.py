"""Redfish live read-transport boundary.

This module is socket-free by injection, exactly like the PiKVM observe
transport: it defines the target/credential/trust shapes and a read-only
transport that talks through an injected ``RedfishHTTPReadClient``. The only
real network implementations live in ``agentickvm.live_validation.redfish``
and are constructed by operator-run harnesses, never by automated tests.

Mutating Redfish verbs (ComputerSystem.Reset, boot override, Manager.Reset)
are refused here fail-closed; the live read transport cannot actuate.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Protocol

from agentickvm.providers.errors import (
    ProviderAuthenticationRequiredError,
    ProviderMutationBlockedError,
    ProviderProtocolError,
    ProviderResponseValidationError,
)
from agentickvm.providers.pikvm_transport import (
    normalize_cert_fingerprint,
    redact_pikvm_observe_payload,
)
from agentickvm.providers.transport_policy import TransportSecurityPolicy
from agentickvm.providers.transports import TransportError

REDFISH_SERVICE_ROOT_PATH = "/redfish/v1/"

# Read operations the live transport supports; the mutating verbs of the
# fixture provider (power.*, boot.override, bmc.reset) are deliberately absent.
REDFISH_LIVE_READ_OPERATIONS = frozenset(
    {
        "observe.status",
        "observe.power_state",
        "observe.hardware_inventory",
        "observe.sensors",
        "observe.event_logs",
        "observe.boot_status",
    }
)


def redact_redfish_read_payload(value: Any) -> Any:
    """Return a Redfish-safe read payload for results and evidence."""

    return redact_pikvm_observe_payload(value)


@dataclass(frozen=True)
class RedfishTargetConfig:
    """Live Redfish BMC connection metadata without credentials."""

    base_url: str
    cert_fingerprint: str | None = None
    verify_ssl: bool = True
    port: int = 443
    connect_timeout_seconds: float = 2.0
    read_timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ProviderProtocolError("Redfish live transport requires https base_url")
        if self.port <= 0:
            raise ProviderProtocolError("Redfish port must be positive")
        if not self.verify_ssl and not self.cert_fingerprint:
            raise ProviderProtocolError(
                "verify_ssl=false is allowed only with cert_fingerprint pinning"
            )
        netloc = self.base_url.removeprefix("https://").split("/", 1)[0]
        if ":" in netloc:
            port_text = netloc.split(":", 1)[1]
            if not port_text.isdigit() or int(port_text) <= 0:
                raise ProviderProtocolError("Redfish base_url port must be a positive integer")
            object.__setattr__(self, "port", int(port_text))

    @property
    def host(self) -> str:
        """Return host component without credentials, port, or path."""

        without_scheme = self.base_url.removeprefix("https://")
        return without_scheme.split("/", 1)[0].split(":", 1)[0]


@dataclass(frozen=True)
class RedfishCredentialRef:
    """Credential reference; raw credential resolution is out of scope here."""

    value: str = field(repr=False)

    def __post_init__(self) -> None:
        if not self.value:
            raise ProviderAuthenticationRequiredError("Redfish credential_ref is required")
        if any(fragment in self.value.lower() for fragment in ("password=", "token=", "secret=")):
            raise ProviderAuthenticationRequiredError(
                "Redfish transport accepts credential references only, not raw secrets"
            )

    def safe_label(self) -> str:
        """Return a non-secret label for result/debug shapes."""

        return "[CREDENTIAL_REF]"


@dataclass(frozen=True)
class RedfishPinnedTrust:
    """Pinned certificate trust root for a Redfish BMC target."""

    sha256_fingerprint: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "sha256_fingerprint",
            normalize_cert_fingerprint(self.sha256_fingerprint),
        )


class RedfishTLSProbe(Protocol):
    """Unauthenticated TLS certificate probe used before credentials exist."""

    def certificate_der_sha256(
        self,
        *,
        host: str,
        port: int,
        timeout_seconds: float,
    ) -> str:
        """Return the peer certificate SHA-256 fingerprint."""


class RedfishHTTPReadClient(Protocol):
    """Authenticated read-only HTTP client created after preflight passes."""

    trust: RedfishPinnedTrust | None

    def get_json(self, path: str, *, timeout_seconds: float) -> Mapping[str, Any]:
        """Return a JSON mapping for a read-only GET path."""


RedfishHTTPClientFactory = Callable[
    [RedfishTargetConfig, RedfishCredentialRef, RedfishPinnedTrust | None],
    RedfishHTTPReadClient,
]


class RedfishFingerprintMismatchError(ProviderProtocolError):
    """Raised when the unauthenticated TLS preflight sees the wrong cert."""


class LiveRedfishReadTransport:
    """Read-only Redfish transport built only after TLS pinning preflight.

    Resource paths are discovered from the service root (Systems, Managers,
    Chassis collections) so the transport works against BMCs that expose
    different member ids (for example ``/redfish/v1/Systems/1`` on Supermicro).
    """

    policy = TransportSecurityPolicy()

    def __init__(
        self,
        *,
        config: RedfishTargetConfig,
        credential_ref: RedfishCredentialRef,
        tls_probe: RedfishTLSProbe,
        http_client_factory: RedfishHTTPClientFactory,
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
        self._resource_cache: dict[str, Mapping[str, Any]] = {}
        trust = self._preflight_pin(tls_probe)
        self.http = http_client_factory(config, credential_ref, trust)

    # -- read operations ---------------------------------------------------

    def service_root(self) -> Mapping[str, Any]:
        """Return the redacted Redfish service root."""

        return self._read_json(REDFISH_SERVICE_ROOT_PATH)

    def status(self) -> Mapping[str, Any]:
        """Return service root and manager status for observe.status."""

        return MappingProxyType(
            {
                "service_root": self.service_root(),
                "manager": self.manager_status(),
            }
        )

    def power_state(self) -> Mapping[str, Any]:
        """Return the system power state."""

        system = self._system_resource()
        return self._summary({"power_state": system.get("PowerState", "Unknown")})

    def boot_status(self) -> Mapping[str, Any]:
        """Return the one-time boot-source override status."""

        system = self._system_resource()
        boot = system.get("Boot", {})
        if not isinstance(boot, Mapping):
            boot = {}
        return self._summary(
            {
                "boot_source_override": boot.get("BootSourceOverrideTarget", "Unknown"),
                "boot_source_override_enabled": boot.get("BootSourceOverrideEnabled", "Unknown"),
            }
        )

    def hardware_inventory(self) -> Mapping[str, Any]:
        """Return a hardware inventory summary from the computer system."""

        system = self._system_resource()
        return self._summary(
            {
                "system_id": system.get("Id"),
                "name": system.get("Name"),
                "manufacturer": system.get("Manufacturer"),
                "model": system.get("Model"),
                "bios_version": system.get("BiosVersion"),
                "processors": system.get("ProcessorSummary", {}),
                "memory": system.get("MemorySummary", {}),
                "status": system.get("Status", {}),
            }
        )

    def sensors(self) -> Mapping[str, Any]:
        """Return thermal/sensor readings from the first chassis."""

        chassis = self._first_member_resource("Chassis", raw=True)
        thermal_ref = _odata_id(chassis.get("Thermal"))
        if thermal_ref:
            thermal = self._read_json(thermal_ref)
            return MappingProxyType(
                {
                    "source": "thermal",
                    "temperatures": list(thermal.get("Temperatures", [])),
                    "fans": list(thermal.get("Fans", [])),
                }
            )
        sensors_ref = _odata_id(chassis.get("Sensors"))
        if sensors_ref:
            sensors = self._read_json(sensors_ref)
            return MappingProxyType(
                {"source": "sensors", "sensors": list(sensors.get("Members", []))}
            )
        raise ProviderResponseValidationError(
            "Redfish chassis exposes neither Thermal nor Sensors resources"
        )

    def event_logs(self) -> Mapping[str, Any]:
        """Return event log entries from the first manager log service."""

        manager = self._first_member_resource("Managers", raw=True)
        log_services_ref = _odata_id(manager.get("LogServices"))
        if not log_services_ref:
            raise ProviderResponseValidationError("Redfish manager exposes no LogServices")
        log_services = self._read_json(log_services_ref, raw=True)
        for member in log_services.get("Members", []):
            member_ref = _odata_id(member)
            if not member_ref:
                continue
            log_service = self._read_json(member_ref, raw=True)
            entries_ref = _odata_id(log_service.get("Entries"))
            if not entries_ref:
                continue
            entries = self._read_json(entries_ref)
            return MappingProxyType(
                {
                    "log_service_id": log_service.get("Id"),
                    "events": list(entries.get("Members", [])),
                }
            )
        raise ProviderResponseValidationError(
            "Redfish manager log services expose no readable Entries"
        )

    def manager_status(self) -> Mapping[str, Any]:
        """Return the first manager (BMC) resource."""

        return self._first_member_resource("Managers")

    # -- mutating verbs are refused fail-closed ----------------------------

    def reset(self, **_ignored: Any) -> Mapping[str, Any]:
        """Refuse ComputerSystem.Reset; this transport is read-only."""

        raise ProviderMutationBlockedError(
            "Redfish live read transport refuses ComputerSystem.Reset; "
            "no mutating verb is implemented"
        )

    def set_boot_override(self, **_ignored: Any) -> Mapping[str, Any]:
        """Refuse boot-source override; this transport is read-only."""

        raise ProviderMutationBlockedError(
            "Redfish live read transport refuses boot override; "
            "no mutating verb is implemented"
        )

    def bmc_reset(self, **_ignored: Any) -> Mapping[str, Any]:
        """Refuse Manager.Reset; this transport is read-only."""

        raise ProviderMutationBlockedError(
            "Redfish live read transport refuses Manager.Reset; "
            "no mutating verb is implemented"
        )

    # -- internals ----------------------------------------------------------

    def _preflight_pin(self, tls_probe: RedfishTLSProbe) -> RedfishPinnedTrust | None:
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
            raise RedfishFingerprintMismatchError(
                "Redfish certificate fingerprint mismatch; credentials were not sent"
            )
        return RedfishPinnedTrust(expected)

    def _summary(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        """Redact a transport-built summary before returning it to callers."""

        return MappingProxyType(dict(redact_redfish_read_payload(dict(payload))))

    def _system_resource(self) -> Mapping[str, Any]:
        # Raw for field extraction only; every public read op redacts the
        # summary it builds from this resource before returning it.
        return self._first_member_resource("Systems", raw=True)

    def _first_member_resource(
        self, collection_key: str, *, raw: bool = False
    ) -> Mapping[str, Any]:
        root = self._read_json(REDFISH_SERVICE_ROOT_PATH, raw=True)
        collection_ref = _odata_id(root.get(collection_key))
        if not collection_ref:
            raise ProviderResponseValidationError(
                f"Redfish service root exposes no {collection_key} collection"
            )
        collection = self._read_json(collection_ref, raw=True)
        members = collection.get("Members", [])
        member_ref = _odata_id(members[0]) if members else None
        if not member_ref:
            raise ProviderResponseValidationError(
                f"Redfish {collection_key} collection has no members"
            )
        return self._read_json(member_ref, raw=raw)

    def _read_json(self, path: str, *, raw: bool = False) -> Mapping[str, Any]:
        cached = self._resource_cache.get(path) if raw else None
        if cached is not None:
            return cached
        try:
            payload = dict(
                self.http.get_json(
                    path,
                    timeout_seconds=self.policy.read_timeout_seconds,
                )
            )
        except TransportError as exc:
            raise ProviderProtocolError("Redfish live read transport error") from exc
        if raw:
            # Raw payloads keep @odata.id references for discovery only; they
            # are cached and never returned to callers unredacted.
            resource = MappingProxyType(payload)
            self._resource_cache[path] = resource
            return resource
        return MappingProxyType(dict(redact_redfish_read_payload(payload)))


def _odata_id(value: Any) -> str | None:
    if isinstance(value, Mapping):
        ref = value.get("@odata.id")
        if isinstance(ref, str) and ref.startswith("/redfish/"):
            return ref
    return None


__all__ = [
    "LiveRedfishReadTransport",
    "REDFISH_LIVE_READ_OPERATIONS",
    "REDFISH_SERVICE_ROOT_PATH",
    "RedfishCredentialRef",
    "RedfishFingerprintMismatchError",
    "RedfishHTTPClientFactory",
    "RedfishHTTPReadClient",
    "RedfishPinnedTrust",
    "RedfishTLSProbe",
    "RedfishTargetConfig",
    "redact_redfish_read_payload",
]
