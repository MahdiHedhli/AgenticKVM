"""PiKVM provider scaffolding.

Live network execution is not implemented here. Fixture-backed observe and
actuation behavior exists so the control-plane clearance seam can be tested
without hardware.
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
from agentickvm.providers.errors import (
    ProviderError,
    ProviderMutationBlockedError,
    ProviderProtocolError,
    ProviderResponseValidationError,
)
from agentickvm.providers.pikvm_calibration import PiKVMScreenshotCalibration
from agentickvm.providers.pikvm_transport import (
    FakePiKVMObserveTransport,
    PIKVM_ATX_POWER_CYCLE_PATH,
    PIKVM_ATX_POWER_OFF_PATH,
    PIKVM_ATX_POWER_ON_PATH,
    PIKVM_ATX_RESET_PATH,
    PIKVM_BOOT_STATUS_PATH,
    PIKVM_EVENT_LOGS_PATH,
    PIKVM_HARDWARE_INVENTORY_PATH,
    PIKVM_HEALTH_PATH,
    PIKVM_HID_KEYBOARD_TYPE_PATH,
    PIKVM_HID_MOUSE_CLICK_PATH,
    PIKVM_HID_MOUSE_MOVE_PATH,
    PIKVM_MSD_MOUNT_PATH,
    PIKVM_POWER_STATE_PATH,
    PIKVM_SCREENSHOT_METADATA_PATH,
    PIKVM_SCREEN_STATE_PATH,
    PiKVMObserveTransport,
)
from agentickvm.providers.transport_policy import TransportSecurityPolicy
from agentickvm.providers.transports import (
    FakeTransport,
    TransportError,
    TransportMethodNotAllowedError,
    TransportRouteNotFoundError,
)

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

PIKVM_ACTUATION_CAPABILITIES = frozenset(
    {
        "power.on",
        "power.force_off",
        "power.power_cycle",
        "power.reset",
        "input.keyboard_type",
        "input.mouse_move",
        "input.mouse_click",
        "media.mount_approved_iso",
    }
)

PIKVM_SUPPORTED_CAPABILITIES = PIKVM_OBSERVE_CAPABILITIES | PIKVM_ACTUATION_CAPABILITIES


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
                    "sensitivity": "sensitive",
                    "content_type": "image/png",
                    "byte_length": 128,
                    "storage": "metadata-only",
                    "target_id": "fixture-target",
                    "artifact_name": "screenshot-fixture-0001.png",
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
            ("POST", PIKVM_ATX_POWER_ON_PATH): {"performed": True, "atx": "power_on"},
            ("POST", PIKVM_ATX_POWER_OFF_PATH): {"performed": True, "atx": "power_off"},
            (
                "POST",
                PIKVM_ATX_POWER_CYCLE_PATH,
            ): {"performed": True, "atx": "power_cycle"},
            ("POST", PIKVM_ATX_RESET_PATH): {"performed": True, "atx": "reset"},
            (
                "POST",
                PIKVM_HID_KEYBOARD_TYPE_PATH,
            ): {"performed": True, "hid": "keyboard_type"},
            ("POST", PIKVM_HID_MOUSE_MOVE_PATH): {"performed": True, "hid": "mouse_move"},
            ("POST", PIKVM_HID_MOUSE_CLICK_PATH): {"performed": True, "hid": "mouse_click"},
            ("POST", PIKVM_MSD_MOUNT_PATH): {"performed": True, "msd": "mount"},
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
        },
        allowed_methods=frozenset({"GET", "POST"}),
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

    def power_on(self) -> Mapping[str, Any]:
        """Fixture ATX power-on actuation."""

        return self._post(PIKVM_ATX_POWER_ON_PATH)

    def power_off(self) -> Mapping[str, Any]:
        """Fixture ATX power-off actuation."""

        return self._post(PIKVM_ATX_POWER_OFF_PATH)

    def power_cycle(self) -> Mapping[str, Any]:
        """Fixture ATX power-cycle actuation."""

        return self._post(PIKVM_ATX_POWER_CYCLE_PATH)

    def reset(self) -> Mapping[str, Any]:
        """Fixture ATX reset actuation."""

        return self._post(PIKVM_ATX_RESET_PATH)

    def type_text(self, *, text: str) -> Mapping[str, Any]:
        """Fixture HID text typing actuation with redacted echo."""

        return self._post(PIKVM_HID_KEYBOARD_TYPE_PATH, params={"text": text})

    def mouse_move(
        self,
        *,
        x: int,
        y: int,
        screen_width: int,
        screen_height: int,
    ) -> Mapping[str, Any]:
        """Fixture HID mouse movement actuation using screenshot calibration."""

        calibrated = PiKVMScreenshotCalibration(
            width=screen_width,
            height=screen_height,
        ).map_point(x=x, y=y)
        return self._post(PIKVM_HID_MOUSE_MOVE_PATH, params=calibrated)

    def mouse_click(
        self,
        *,
        x: int,
        y: int,
        screen_width: int,
        screen_height: int,
        button: str = "left",
    ) -> Mapping[str, Any]:
        """Fixture HID mouse click actuation using screenshot calibration."""

        calibrated = PiKVMScreenshotCalibration(
            width=screen_width,
            height=screen_height,
        ).map_point(x=x, y=y)
        return self._post(PIKVM_HID_MOUSE_CLICK_PATH, params={**calibrated, "button": button})

    def mount_msd(self, *, image_ref: str) -> Mapping[str, Any]:
        """Fixture MSD image mount actuation."""

        return self._post(PIKVM_MSD_MOUNT_PATH, params={"image_ref": image_ref})

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

    def _post(self, path: str, *, params: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        try:
            payload = dict(
                self.transport.request(
                    "POST",
                    path,
                    params=params or {},
                    timeout_seconds=self.timeout_seconds,
                ).json()
            )
        except TransportMethodNotAllowedError as exc:
            raise ProviderMutationBlockedError(
                "PiKVM fake transport rejected actuation method"
            ) from exc
        except TransportRouteNotFoundError as exc:
            raise ProviderResponseValidationError(
                f"PiKVM fake fixture route missing: {path}"
            ) from exc
        except TransportError as exc:
            raise ProviderProtocolError("PiKVM fake actuation transport error") from exc
        return MappingProxyType(dict(payload))


class PiKVMObserveProvider(Provider):
    """PiKVM adapter for fixture-backed observe and actuation tests."""

    provider_kind = "pikvm"
    supported_capabilities = PIKVM_SUPPORTED_CAPABILITIES

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
            else "test_fake_clearance_gated"
        )

    def status(self) -> ProviderStatus:
        """Return local provider status without contacting a target."""

        status = super().status()
        message = (
            "PiKVM provider is fixture-backed; actuation requires ControlPlane clearance"
            if self.client is not None and self.enabled
            else "PiKVM provider is disabled; no live transport exists"
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
                message="PiKVM provider has no fake transport",
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
            elif request.capability == "power.on":
                data = {"actuation": self.client.power_on()}
            elif request.capability == "power.force_off":
                data = {"actuation": self.client.power_off()}
            elif request.capability == "power.power_cycle":
                data = {"actuation": self.client.power_cycle()}
            elif request.capability == "power.reset":
                data = {"actuation": self.client.reset()}
            elif request.capability == "input.keyboard_type":
                data = {
                    "actuation": self.client.type_text(
                        text=str(request.parameters.get("text", ""))
                    ),
                    "parameters": request.redacted_parameters(),
                }
            elif request.capability == "input.mouse_move":
                data = {
                    "actuation": self.client.mouse_move(
                        x=int(request.parameters.get("x", 0)),
                        y=int(request.parameters.get("y", 0)),
                        screen_width=int(request.parameters.get("screen_width", 1280)),
                        screen_height=int(request.parameters.get("screen_height", 720)),
                    ),
                }
            elif request.capability == "input.mouse_click":
                data = {
                    "actuation": self.client.mouse_click(
                        x=int(request.parameters.get("x", 0)),
                        y=int(request.parameters.get("y", 0)),
                        screen_width=int(request.parameters.get("screen_width", 1280)),
                        screen_height=int(request.parameters.get("screen_height", 720)),
                        button=str(request.parameters.get("button", "left")),
                    ),
                }
            elif request.capability == "media.mount_approved_iso":
                data = {
                    "actuation": self.client.mount_msd(
                        image_ref=str(request.parameters.get("image_ref", ""))
                    )
                }
            else:
                return self._result(
                    request,
                    ok=False,
                    message="Unsupported PiKVM capability",
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
            message="PiKVM fixture operation completed; no hardware action performed.",
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
    "PIKVM_ACTUATION_CAPABILITIES",
    "PIKVM_OBSERVE_CAPABILITIES",
    "PIKVM_SUPPORTED_CAPABILITIES",
    "PiKVMObserveClient",
    "PiKVMObserveProvider",
    "default_pikvm_fake_transport",
]
