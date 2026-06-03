"""PiKVM observe-only provider scaffolding.

Only fixture-backed observe behavior is implemented here. No live transport,
credentials, input, power, media, boot, storage, network, or BMC mutation
behavior exists in this module.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from agentickvm.providers.base import (
    Provider,
    ProviderActionRequest,
    ProviderActionResult,
    ProviderStatus,
    ProviderValidationResult,
)
from agentickvm.providers.errors import ProviderError
from agentickvm.providers.pikvm_transport import (
    FakePiKVMObserveTransport,
    PIKVM_BOOT_STATUS_PATH,
    PIKVM_EVENT_LOGS_PATH,
    PIKVM_HARDWARE_INVENTORY_PATH,
    PIKVM_HEALTH_PATH,
    PIKVM_POWER_STATE_PATH,
    PIKVM_SCREENSHOT_METADATA_PATH,
    PIKVM_SCREEN_STATE_PATH,
    PiKVMObserveTransport,
)
from agentickvm.providers.transport_policy import TransportSecurityPolicy
from agentickvm.providers.transports import FakeTransport

PIKVM_OBSERVE_CAPABILITIES = frozenset(
    {
        "observe.status",
        "observe.screen",
        "observe.screenshot",
        "observe.power_state",
        "observe.hardware_inventory",
        "observe.event_logs",
        "observe.boot_status",
    }
)


def default_pikvm_fake_transport() -> FakeTransport:
    """Return deterministic PiKVM fixture responses for tests."""

    return FakeTransport(
        {
            (
                "GET",
                PIKVM_HEALTH_PATH,
            ): {
                "health": "ok",
                "fixture": True,
                "transport": "fake",
                "streamer": {"state": "online", "resolution": "1280x720"},
                "atx": {"power": "on"},
            },
            (
                "GET",
                PIKVM_SCREEN_STATE_PATH,
            ): {
                "kind": "text_snapshot",
                "content": "PiKVM fixture screen",
                "sensitive": True,
                "source": "synthetic-fixture",
            },
            (
                "GET",
                PIKVM_SCREENSHOT_METADATA_PATH,
            ): {
                "artifact": {
                    "kind": "screenshot",
                    "content_type": "image/png",
                    "byte_length": 128,
                    "storage": "metadata-only",
                    "target_id": "fixture-target",
                },
                "sensitive": True,
                "raw_bytes_included": False,
            },
            ("GET", PIKVM_POWER_STATE_PATH): {"power_state": "on"},
            ("GET", PIKVM_BOOT_STATUS_PATH): {"boot_status": "firmware_prompt"},
            (
                "GET",
                PIKVM_HARDWARE_INVENTORY_PATH,
            ): {
                "provider": "pikvm",
                "model": "PiKVM fixture",
                "capture": "fixture",
            },
            (
                "GET",
                PIKVM_EVENT_LOGS_PATH,
            ): {
                "events": [
                    {
                        "severity": "info",
                        "message": "fixture streamer online",
                    }
                ]
            },
            (
                "GET",
                "/api/status",
            ): {
                "health": "ok",
                "streamer": {"state": "online", "resolution": "1280x720"},
                "atx": {"power": "on"},
            },
            (
                "GET",
                "/api/screen",
            ): {
                "kind": "text_snapshot",
                "content": "PiKVM fixture screen",
                "sensitive": True,
            },
            ("GET", "/api/power"): {"power_state": "on"},
            ("GET", "/api/boot"): {"boot_status": "firmware_prompt"},
            (
                "GET",
                "/api/inventory",
            ): {
                "provider": "pikvm",
                "model": "PiKVM fixture",
                "capture": "fixture",
            },
            (
                "GET",
                "/api/events",
            ): {
                "events": [
                    {
                        "severity": "info",
                        "message": "fixture streamer online",
                    }
                ]
            },
        }
    )


class PiKVMObserveClient:
    """PiKVM observe-only client using an injected fake transport."""

    def __init__(
        self,
        *,
        transport: FakeTransport | None = None,
        observe_transport: PiKVMObserveTransport | None = None,
        policy: TransportSecurityPolicy | None = None,
        timeout_seconds: float = 2.0,
    ) -> None:
        if transport is None and observe_transport is None:
            raise ValueError("PiKVM observe client requires an injected fake transport")
        self.transport = transport or getattr(observe_transport, "transport", None)
        self.observe_transport = observe_transport or FakePiKVMObserveTransport(
            transport=transport,
            policy=policy or TransportSecurityPolicy(read_timeout_seconds=timeout_seconds),
        )
        self.timeout_seconds = timeout_seconds

    def status(self) -> Mapping[str, Any]:
        """Read fake PiKVM status."""

        return self.observe_transport.get_health()

    def screen(self) -> Mapping[str, Any]:
        """Read fake PiKVM screen metadata."""

        return self.observe_transport.get_screen_state()

    def screenshot_metadata(self) -> Mapping[str, Any]:
        """Read fake PiKVM screenshot artifact metadata."""

        return self.observe_transport.get_screenshot_metadata()

    def power_state(self) -> Mapping[str, Any]:
        """Read fake PiKVM power state."""

        return self.observe_transport.get_power_state()

    def boot_status(self) -> Mapping[str, Any]:
        """Read fake PiKVM boot status."""

        return self.observe_transport.get_boot_status()

    def hardware_inventory(self) -> Mapping[str, Any]:
        """Read fake PiKVM inventory."""

        return self.observe_transport.get_hardware_inventory()

    def event_logs(self) -> Mapping[str, Any]:
        """Read fake PiKVM event logs."""

        return self.observe_transport.get_event_logs()

    def _get(self, path: str) -> Mapping[str, Any]:
        return MappingProxyType(
            dict(
                self.transport.request(
                    "GET",
                    path,
                    timeout_seconds=self.timeout_seconds,
                ).json()
            )
        )


class PiKVMObserveProvider(Provider):
    """Observe-only PiKVM adapter for fixture-backed tests."""

    provider_kind = "pikvm"
    supported_capabilities = PIKVM_OBSERVE_CAPABILITIES

    def __init__(
        self,
        *,
        provider_id: str = "pikvm-fixture",
        client: PiKVMObserveClient | None = None,
        enabled: bool = False,
    ) -> None:
        self.provider_id = provider_id
        self.enabled = enabled
        self.client = client
        self.requests: list[ProviderActionRequest] = []
        self.is_real_hardware = client is None
        self.risk_class = (
            "real_hardware_disabled"
            if client is None
            else "test_fake_observe_only"
        )

    def status(self) -> ProviderStatus:
        """Return local provider status without contacting a target."""

        status = super().status()
        message = (
            "PiKVM observe provider is fixture-backed"
            if self.client is not None and self.enabled
            else "PiKVM observe provider is disabled; no live transport exists"
        )
        return ProviderStatus(
            provider_id=status.provider_id,
            provider_kind=status.provider_kind,
            enabled=status.enabled,
            is_real_hardware=status.is_real_hardware,
            risk_class=status.risk_class,
            supported_capabilities=status.supported_capabilities,
            message=message,
        )

    def validate_authorized(
        self,
        request: ProviderActionRequest,
    ) -> ProviderValidationResult:
        """Validate fixture-backed observe execution."""

        if self.client is None:
            return ProviderValidationResult(
                ok=False,
                provider_id=self.provider_id,
                capability=request.capability,
                message="PiKVM observe provider has no fake transport",
            )
        return super().validate_authorized(request)

    def execute_authorized(
        self,
        request: ProviderActionRequest,
    ) -> ProviderActionResult:
        validation = self.validate_authorized(request)
        if not validation.ok:
            return self._result(request, ok=False, message=validation.message)

        self.requests.append(request)
        try:
            if request.capability == "observe.status":
                data = {"status": self.client.status()}
            elif request.capability == "observe.screen":
                data = {"screen": self.client.screen()}
            elif request.capability == "observe.screenshot":
                data = {
                    "screen": self.client.screen(),
                    "screenshot": self.client.screenshot_metadata(),
                }
            elif request.capability == "observe.power_state":
                data = {"power_state": self.client.power_state()["power_state"]}
            elif request.capability == "observe.hardware_inventory":
                data = {"inventory": self.client.hardware_inventory()}
            elif request.capability == "observe.event_logs":
                data = {"events": list(self.client.event_logs()["events"])}
            elif request.capability == "observe.boot_status":
                data = {"boot_status": self.client.boot_status()["boot_status"]}
            else:
                return self._result(
                    request,
                    ok=False,
                    message="Unsupported PiKVM observe-only capability",
                )
        except ProviderError as exc:
            return exc.to_provider_result(
                request=request,
                provider_id=self.provider_id,
                provider_type=self.provider_kind,
            )

        safe_data = {
            "provider": "pikvm",
            "fixture": True,
            "performed": False,
            **data,
        }
        return self._result(
            request,
            ok=True,
            message="PiKVM fixture observation completed; no hardware action performed.",
            data=safe_data,
        )

    def _result(
        self,
        request: ProviderActionRequest,
        *,
        ok: bool,
        message: str,
        data: Mapping[str, Any] | None = None,
    ) -> ProviderActionResult:
        return ProviderActionResult(
            ok=ok,
            provider_id=self.provider_id,
            capability=request.capability,
            action=request.action,
            target_id=request.target_id,
            performed_on_hardware=False,
            message=message,
            data=data or {"provider": "pikvm", "fixture": True, "performed": False},
            provider_type=self.provider_kind,
            error_code=None if ok else "unsupported_capability",
            error_message=None if ok else message,
        )


__all__ = [
    "PIKVM_OBSERVE_CAPABILITIES",
    "PiKVMObserveClient",
    "PiKVMObserveProvider",
    "default_pikvm_fake_transport",
]
