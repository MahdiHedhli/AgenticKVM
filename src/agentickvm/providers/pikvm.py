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
        transport: FakeTransport,
        timeout_seconds: float = 2.0,
    ) -> None:
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def status(self) -> Mapping[str, Any]:
        """Read fake PiKVM status."""

        return self._get("/api/status")

    def screen(self) -> Mapping[str, Any]:
        """Read fake PiKVM screen metadata."""

        return self._get("/api/screen")

    def power_state(self) -> Mapping[str, Any]:
        """Read fake PiKVM power state."""

        return self._get("/api/power")

    def boot_status(self) -> Mapping[str, Any]:
        """Read fake PiKVM boot status."""

        return self._get("/api/boot")

    def hardware_inventory(self) -> Mapping[str, Any]:
        """Read fake PiKVM inventory."""

        return self._get("/api/inventory")

    def event_logs(self) -> Mapping[str, Any]:
        """Read fake PiKVM event logs."""

        return self._get("/api/events")

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
        self.requests.append(request)
        validation = self.validate_authorized(request)
        if not validation.ok:
            return self._result(request, ok=False, message=validation.message)

        if request.capability == "observe.status":
            data = {"status": self.client.status()}
        elif request.capability in {"observe.screen", "observe.screenshot"}:
            data = {"screen": self.client.screen()}
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
        )


__all__ = [
    "PIKVM_OBSERVE_CAPABILITIES",
    "PiKVMObserveClient",
    "PiKVMObserveProvider",
    "default_pikvm_fake_transport",
]
