"""Safe mock provider for tests and bootstrap development."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentickvm.control_plane.capabilities import DEFAULT_CAPABILITY_REGISTRY
from agentickvm.providers.base import (
    Provider,
    ProviderActionRequest,
    ProviderActionResult,
)


@dataclass
class MockProviderState:
    """In-memory fake target state."""

    power_state: str = "off"
    screen_text: str = "AgenticKVM mock screen"
    mounted_media: str | None = None
    boot_override: str | None = None
    input_events: list[dict[str, Any]] = field(default_factory=list)
    simulated_events: list[dict[str, Any]] = field(default_factory=list)
    network_config: dict[str, Any] = field(
        default_factory=lambda: {"bmc_ip": "192.0.2.10", "host_ip": "192.0.2.20"}
    )
    storage_layout: dict[str, Any] = field(
        default_factory=lambda: {"disks": [{"id": "mock-disk-0", "size_gb": 64}]}
    )


class MockProvider(Provider):
    """Provider placeholder that never contacts real hardware."""

    provider_id = "mock"
    provider_kind = "mock"
    is_real_hardware = False
    supported_capabilities = frozenset(DEFAULT_CAPABILITY_REGISTRY.capabilities)

    def __init__(self) -> None:
        self.requests: list[ProviderActionRequest] = []
        self.state = MockProviderState()

    def execute_authorized(
        self,
        request: ProviderActionRequest,
    ) -> ProviderActionResult:
        self.requests.append(request)

        if not self.supports(request.capability):
            return ProviderActionResult(
                ok=False,
                provider_id=self.provider_id,
                capability=request.capability,
                action=request.action,
                target_id=request.target_id,
                performed_on_hardware=False,
                message="Unsupported mock capability; no hardware action performed.",
                data={"mock": True, "performed": False},
            )

        data = self._simulate(request)
        return ProviderActionResult(
            ok=True,
            provider_id=self.provider_id,
            capability=request.capability,
            action=request.action,
            target_id=request.target_id,
            performed_on_hardware=False,
            message="Mock provider recorded authorized request; no hardware action performed.",
            data=data,
        )

    def _simulate(self, request: ProviderActionRequest) -> dict[str, Any]:
        parameters = dict(request.redacted_parameters())
        data: dict[str, Any] = {
            "mock": True,
            "simulated": True,
            "performed": False,
            "parameters": parameters,
        }

        if request.capability == "observe.status":
            data["state"] = self._state_summary()
        elif request.capability == "observe.screenshot":
            data["screen"] = {
                "kind": "text_snapshot",
                "content": self.state.screen_text,
            }
        elif request.capability == "observe.power_state":
            data["power_state"] = self.state.power_state
        elif request.capability == "observe.hardware_inventory":
            data["inventory"] = {
                "provider": "mock",
                "model": "AgenticKVM Mock Target",
            }
        elif request.capability == "observe.sensors":
            data["sensors"] = [{"name": "mock-temp", "value": 25, "unit": "C"}]
        elif request.capability == "observe.event_logs":
            data["events"] = list(self.state.simulated_events)
        elif request.capability.startswith("input."):
            event = {"capability": request.capability, "parameters": parameters}
            self.state.input_events.append(event)
            data["input_events"] = list(self.state.input_events)
        elif request.capability == "power.on":
            self.state.power_state = "on"
            data["power_state"] = self.state.power_state
        elif request.capability in {"power.graceful_shutdown", "power.force_off"}:
            self.state.power_state = "off"
            self._record_simulated_event(request)
            data["power_state"] = self.state.power_state
        elif request.capability == "power.force_restart":
            self.state.power_state = "on"
            self._record_simulated_event(request)
            data["power_state"] = self.state.power_state
        elif request.capability == "power.nmi":
            self._record_simulated_event(request)
            data["power_state"] = self.state.power_state
        elif request.capability in {"media.mount_approved_iso", "media.mount_arbitrary_iso"}:
            self.state.mounted_media = str(
                parameters.get("image")
                or parameters.get("url")
                or parameters.get("media")
                or "mock.iso"
            )
            self._record_simulated_event(request)
            data["mounted_media"] = self.state.mounted_media
        elif request.capability == "media.eject":
            self.state.mounted_media = None
            data["mounted_media"] = None
        elif request.capability == "boot.override":
            self.state.boot_override = str(parameters.get("device", "mock-override"))
            self._record_simulated_event(request)
            data["boot_override"] = self.state.boot_override
        elif request.capability.startswith("bios.") or request.capability.startswith("firmware."):
            self._record_simulated_event(request)
            data["event"] = self.state.simulated_events[-1]
        elif request.capability == "storage.view_disk_layout":
            data["storage_layout"] = self.state.storage_layout
        elif request.capability.startswith("storage."):
            self._record_simulated_event(request)
            data["storage_layout"] = self.state.storage_layout
            data["destructive_effect_simulated"] = True
        elif request.capability == "network.read_config":
            data["network_config"] = dict(self.state.network_config)
        elif request.capability.startswith("network."):
            self._record_simulated_event(request)
            data["network_config"] = dict(self.state.network_config)
        elif request.capability.startswith("bmc."):
            self._record_simulated_event(request)
            data["event"] = self.state.simulated_events[-1]
        elif request.capability.startswith("secrets."):
            self._record_simulated_event(request)
            data["secret_material_revealed"] = False
        elif request.capability.startswith("runtime."):
            self._record_simulated_event(request)
            data["runtime"] = {"status": "simulated"}

        return data

    def _state_summary(self) -> dict[str, Any]:
        return {
            "power_state": self.state.power_state,
            "mounted_media": self.state.mounted_media,
            "boot_override": self.state.boot_override,
            "input_event_count": len(self.state.input_events),
            "simulated_event_count": len(self.state.simulated_events),
        }

    def _record_simulated_event(self, request: ProviderActionRequest) -> None:
        self.state.simulated_events.append(
            {
                "capability": request.capability,
                "action": request.action,
                "target_id": request.target_id,
                "simulated": True,
            }
        )
