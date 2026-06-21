"""Redfish provider scaffolding.

Live network execution is not implemented here. Fixture-backed observe and
actuation behavior exists so the control-plane clearance seam can be tested
without hardware. Redfish actuation is power, boot-override, and BMC reset
(there is no HID input surface, unlike PiKVM).
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
from agentickvm.providers.transports import (
    FakeTransport,
    TransportError,
    TransportMethodNotAllowedError,
    TransportRouteNotFoundError,
)

REDFISH_SYSTEM_PATH = "/redfish/v1/Systems/System.Embedded.1"
REDFISH_RESET_ACTION_PATH = "/redfish/v1/Systems/System.Embedded.1/Actions/ComputerSystem.Reset"
REDFISH_MANAGER_RESET_PATH = "/redfish/v1/Managers/1/Actions/Manager.Reset"

REDFISH_OBSERVE_CAPABILITIES = frozenset(
    {
        "observe.status",
        "observe.power_state",
        "observe.hardware_inventory",
        "observe.sensors",
        "observe.event_logs",
        "observe.boot_status",
    }
)

REDFISH_ACTUATION_CAPABILITIES = frozenset(
    {
        "power.on",
        "power.force_off",
        "power.graceful_shutdown",
        "power.graceful_restart",
        "power.force_restart",
        "power.power_cycle",
        "power.nmi",
        "boot.override",
        "bmc.reset",
    }
)

REDFISH_SUPPORTED_CAPABILITIES = REDFISH_OBSERVE_CAPABILITIES | REDFISH_ACTUATION_CAPABILITIES

# Map AgenticKVM power capabilities to Redfish ComputerSystem.Reset ResetType values.
_REDFISH_RESET_TYPES = {
    "power.on": "On",
    "power.force_off": "ForceOff",
    "power.graceful_shutdown": "GracefulShutdown",
    "power.graceful_restart": "GracefulRestart",
    "power.force_restart": "ForceRestart",
    "power.power_cycle": "PowerCycle",
    "power.nmi": "Nmi",
}


def default_redfish_fake_transport() -> FakeTransport:
    """Return deterministic Redfish fixture responses for tests."""

    return FakeTransport(
        {
            (
                "GET",
                "/redfish/v1/",
            ): {
                "RedfishVersion": "1.17.0",
                "Systems": {"@odata.id": "/redfish/v1/Systems"},
                "Managers": {"@odata.id": "/redfish/v1/Managers"},
            },
            (
                "GET",
                "/redfish/v1/Systems",
            ): {
                "Members": [{"@odata.id": "/redfish/v1/Systems/System.Embedded.1"}],
                "Members@odata.count": 1,
            },
            (
                "GET",
                REDFISH_SYSTEM_PATH,
            ): {
                "Id": "System.Embedded.1",
                "Name": "Redfish fixture system",
                "PowerState": "On",
                "Status": {"State": "Enabled", "Health": "OK"},
                "Boot": {"BootSourceOverrideTarget": "None"},
                "ProcessorSummary": {"Count": 2},
                "MemorySummary": {"TotalSystemMemoryGiB": 64},
            },
            (
                "GET",
                "/redfish/v1/Chassis/1/Sensors",
            ): {
                "Members": [
                    {
                        "Name": "CPU Temp",
                        "Reading": 38,
                        "ReadingUnits": "C",
                        "Status": {"Health": "OK"},
                    }
                ]
            },
            (
                "GET",
                "/redfish/v1/Managers/1/LogServices/EventLog/Entries",
            ): {
                "Members": [
                    {
                        "Severity": "OK",
                        "Message": "Fixture event log entry",
                    }
                ]
            },
            (
                "GET",
                "/redfish/v1/Managers/1",
            ): {
                "Id": "1",
                "Name": "Fixture BMC",
                "Status": {"State": "Enabled", "Health": "OK"},
            },
            (
                "POST",
                REDFISH_RESET_ACTION_PATH,
            ): {"performed": True, "action": "ComputerSystem.Reset"},
            (
                "PATCH",
                REDFISH_SYSTEM_PATH,
            ): {"performed": True, "action": "BootOverride"},
            (
                "POST",
                REDFISH_MANAGER_RESET_PATH,
            ): {"performed": True, "action": "Manager.Reset"},
        },
        allowed_methods=frozenset({"GET", "POST", "PATCH"}),
    )


class RedfishObserveClient:
    """Redfish client using an injected fake transport for observe + actuation."""

    def __init__(
        self,
        *,
        transport: FakeTransport,
        timeout_seconds: float = 2.0,
    ) -> None:
        self.transport = transport
        self.timeout_seconds = timeout_seconds

    def service_root(self) -> Mapping[str, Any]:
        """Read fake Redfish service root."""

        return self._get("/redfish/v1/")

    def systems_collection(self) -> Mapping[str, Any]:
        """Read fake systems collection."""

        return self._get("/redfish/v1/Systems")

    def computer_system(self) -> Mapping[str, Any]:
        """Read fake primary computer system."""

        return self._get(REDFISH_SYSTEM_PATH)

    def power_state(self) -> Mapping[str, Any]:
        """Read fake power state."""

        system = self.computer_system()
        return MappingProxyType({"power_state": system.get("PowerState", "Unknown")})

    def hardware_inventory(self) -> Mapping[str, Any]:
        """Read fake hardware inventory summary."""

        system = self.computer_system()
        return MappingProxyType(
            {
                "system_id": system.get("Id"),
                "name": system.get("Name"),
                "processors": system.get("ProcessorSummary", {}),
                "memory": system.get("MemorySummary", {}),
            }
        )

    def sensors(self) -> Mapping[str, Any]:
        """Read fake sensors summary."""

        return self._get("/redfish/v1/Chassis/1/Sensors")

    def event_logs(self) -> Mapping[str, Any]:
        """Read fake event log entries."""

        return self._get("/redfish/v1/Managers/1/LogServices/EventLog/Entries")

    def boot_status(self) -> Mapping[str, Any]:
        """Read fake boot status."""

        system = self.computer_system()
        boot = system.get("Boot", {})
        return MappingProxyType(
            {"boot_source_override": boot.get("BootSourceOverrideTarget", "Unknown")}
        )

    def manager_status(self) -> Mapping[str, Any]:
        """Read fake manager status."""

        return self._get("/redfish/v1/Managers/1")

    def reset(self, *, reset_type: str) -> Mapping[str, Any]:
        """Fixture ComputerSystem.Reset actuation."""

        return self._post(REDFISH_RESET_ACTION_PATH, params={"ResetType": reset_type})

    def set_boot_override(self, *, target: str) -> Mapping[str, Any]:
        """Fixture one-time boot-source override actuation."""

        return self._patch(
            REDFISH_SYSTEM_PATH,
            params={"Boot": {"BootSourceOverrideTarget": target}},
        )

    def bmc_reset(self) -> Mapping[str, Any]:
        """Fixture Manager.Reset (BMC reset) actuation."""

        return self._post(REDFISH_MANAGER_RESET_PATH, params={"ResetType": "GracefulRestart"})

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
        return self._mutate("POST", path, params=params)

    def _patch(self, path: str, *, params: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        return self._mutate("PATCH", path, params=params)

    def _mutate(
        self, method: str, path: str, *, params: Mapping[str, Any] | None
    ) -> Mapping[str, Any]:
        try:
            payload = dict(
                self.transport.request(
                    method,
                    path,
                    params=params or {},
                    timeout_seconds=self.timeout_seconds,
                ).json()
            )
        except TransportMethodNotAllowedError as exc:
            raise ProviderMutationBlockedError(
                "Redfish fake transport rejected actuation method"
            ) from exc
        except TransportRouteNotFoundError as exc:
            raise ProviderResponseValidationError(
                f"Redfish fake fixture route missing: {path}"
            ) from exc
        except TransportError as exc:
            raise ProviderProtocolError("Redfish fake actuation transport error") from exc
        return MappingProxyType(dict(payload))


class RedfishObserveProvider(Provider):
    """Redfish adapter for fixture-backed observe and actuation tests."""

    provider_kind = "redfish"
    supported_capabilities = REDFISH_SUPPORTED_CAPABILITIES

    def __init__(
        self,
        *,
        provider_id: str = "redfish-fixture",
        client: RedfishObserveClient | None = None,
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
            "Redfish provider is fixture-backed; actuation requires ControlPlane clearance"
            if self.client is not None and self.enabled
            else "Redfish provider is disabled; no live transport exists"
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
                message="Redfish provider has no fake transport",
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
                data = {
                    "service_root": self.client.service_root(),
                    "manager": self.client.manager_status(),
                }
            elif request.capability == "observe.power_state":
                data = {"power_state": self.client.power_state()["power_state"]}
            elif request.capability == "observe.hardware_inventory":
                data = {"inventory": self.client.hardware_inventory()}
            elif request.capability == "observe.sensors":
                data = {"sensors": list(self.client.sensors()["Members"])}
            elif request.capability == "observe.event_logs":
                data = {"events": list(self.client.event_logs()["Members"])}
            elif request.capability == "observe.boot_status":
                data = {"boot_status": self.client.boot_status()}
            elif request.capability in _REDFISH_RESET_TYPES:
                data = {
                    "actuation": self.client.reset(
                        reset_type=_REDFISH_RESET_TYPES[request.capability]
                    )
                }
            elif request.capability == "boot.override":
                data = {
                    "actuation": self.client.set_boot_override(
                        target=str(request.parameters.get("boot_target", "Pxe"))
                    ),
                    "parameters": request.redacted_parameters(),
                }
            elif request.capability == "bmc.reset":
                data = {"actuation": self.client.bmc_reset()}
            else:
                return self._result(
                    request,
                    ok=False,
                    message="Unsupported Redfish capability",
                )
        except ProviderError as exc:
            return exc.to_provider_result(
                request=request,
                provider_id=self.provider_id,
                provider_type=self.provider_kind,
            )

        safe_data = {
            "provider": "redfish",
            "fixture": True,
            "performed": False,
            **data,
        }
        return self._result(
            request,
            ok=True,
            message="Redfish fixture operation completed; no hardware action performed.",
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
            data=data or {"provider": "redfish", "fixture": True, "performed": False},
            provider_type=self.provider_kind,
            error_code=None if ok else "unsupported_capability",
            error_message=None if ok else message,
        )


__all__ = [
    "REDFISH_ACTUATION_CAPABILITIES",
    "REDFISH_OBSERVE_CAPABILITIES",
    "REDFISH_SUPPORTED_CAPABILITIES",
    "RedfishObserveClient",
    "RedfishObserveProvider",
    "default_redfish_fake_transport",
]
