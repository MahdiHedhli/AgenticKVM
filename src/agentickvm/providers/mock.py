"""Safe mock provider for tests and bootstrap development."""

from __future__ import annotations

from agentickvm.providers.base import (
    Provider,
    ProviderActionRequest,
    ProviderActionResult,
)


class MockProvider(Provider):
    """Provider placeholder that never contacts real hardware."""

    provider_id = "mock"
    provider_kind = "mock"
    is_real_hardware = False
    supported_capabilities = frozenset(
        {
            "session.start",
            "observe.status",
            "input.keyboard_type",
            "runtime.noop",
            "power.force_off",
            "media.eject",
        }
    )

    def __init__(self) -> None:
        self.requests: list[ProviderActionRequest] = []

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

        return ProviderActionResult(
            ok=True,
            provider_id=self.provider_id,
            capability=request.capability,
            action=request.action,
            target_id=request.target_id,
            performed_on_hardware=False,
            message="Mock provider recorded authorized request; no hardware action performed.",
            data={
                "mock": True,
                "performed": False,
                "parameters": dict(request.redacted_parameters()),
            },
        )
