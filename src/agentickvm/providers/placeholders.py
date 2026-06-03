"""Disabled real-provider placeholders.

These classes are contract markers only. They do not make network calls and
cannot execute provider actions.
"""

from __future__ import annotations

from agentickvm.providers.base import (
    Provider,
    ProviderActionRequest,
    ProviderActionResult,
    ProviderStatus,
    ProviderValidationResult,
)

OBSERVE_ONLY_REAL_PROVIDER_CAPABILITIES = frozenset(
    {
        "observe.power_state",
        "observe.hardware_inventory",
        "observe.sensors",
        "observe.event_logs",
        "observe.boot_status",
        "observe.screenshot",
    }
)


class RealProviderNotEnabledError(RuntimeError):
    """Raised when a disabled real-provider placeholder is asked to execute."""


class DisabledRealProviderPlaceholder(Provider):
    """Base disabled placeholder for a future real provider."""

    enabled = False
    is_real_hardware = True
    risk_class = "real_hardware_disabled"
    supported_capabilities = OBSERVE_ONLY_REAL_PROVIDER_CAPABILITIES

    def __init__(self, *, provider_id: str, provider_kind: str) -> None:
        self.provider_id = provider_id
        self.provider_kind = provider_kind

    def status(self) -> ProviderStatus:
        """Return disabled local status without contacting hardware."""

        status = super().status()
        return ProviderStatus(
            provider_id=status.provider_id,
            provider_kind=status.provider_kind,
            enabled=status.enabled,
            is_real_hardware=status.is_real_hardware,
            risk_class=status.risk_class,
            supported_capabilities=status.supported_capabilities,
            message="real provider placeholder is disabled; no network calls performed",
        )

    def validate_authorized(
        self,
        request: ProviderActionRequest,
    ) -> ProviderValidationResult:
        """Fail validation because placeholders are disabled."""

        return ProviderValidationResult(
            ok=False,
            provider_id=self.provider_id,
            capability=request.capability,
            message="real provider placeholder is disabled",
        )

    def execute_authorized(
        self,
        request: ProviderActionRequest,
    ) -> ProviderActionResult:
        raise RealProviderNotEnabledError(
            f"Real provider placeholder is disabled: {self.provider_id}"
        )


class PiKVMProviderPlaceholder(DisabledRealProviderPlaceholder):
    """Disabled PiKVM provider placeholder."""

    def __init__(self, *, provider_id: str = "pikvm-placeholder") -> None:
        super().__init__(provider_id=provider_id, provider_kind="pikvm")


class RedfishProviderPlaceholder(DisabledRealProviderPlaceholder):
    """Disabled Redfish provider placeholder."""

    def __init__(self, *, provider_id: str = "redfish-placeholder") -> None:
        super().__init__(provider_id=provider_id, provider_kind="redfish")


__all__ = [
    "DisabledRealProviderPlaceholder",
    "OBSERVE_ONLY_REAL_PROVIDER_CAPABILITIES",
    "PiKVMProviderPlaceholder",
    "RealProviderNotEnabledError",
    "RedfishProviderPlaceholder",
]
