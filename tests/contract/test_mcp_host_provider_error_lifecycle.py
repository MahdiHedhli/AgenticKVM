import json
from pathlib import Path

import pytest

from agentickvm.config import ConfigRuntime, mock_only_config
from agentickvm.control_plane import (
    ApprovalStore,
    ControlMode,
    DEFAULT_CAPABILITY_REGISTRY,
    InMemoryAuditSink,
    TargetDefinition,
    TargetRegistry,
    mode_preset,
)
from agentickvm.mcp_sdk import MCPHostCompatibilityLayer
from agentickvm.providers import Provider, ProviderActionRequest, ProviderActionResult
from agentickvm.providers.errors import (
    ProviderAuthenticationFailedError,
    ProviderAuthenticationRequiredError,
    ProviderAuthorizationError,
    ProviderConnectionError,
    ProviderError,
    ProviderMutationBlockedError,
    ProviderProtocolError,
    ProviderRateLimitedError,
    ProviderResponseValidationError,
    ProviderTLSVerificationError,
    ProviderTimeoutError,
    ProviderUnsafeOperationError,
    UnsupportedCapabilityError,
)
from agentickvm.providers.registry import ProviderEntry, ProviderRegistry

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = json.loads(
    (
        ROOT
        / "tests"
        / "fixtures"
        / "mcp_host"
        / "provider_errors"
        / "scenarios.json"
    ).read_text(encoding="utf-8")
)

ERROR_TYPES: dict[str, type[ProviderError]] = {
    "provider_timeout": ProviderTimeoutError,
    "provider_tls_verification": ProviderTLSVerificationError,
    "provider_authentication_required": ProviderAuthenticationRequiredError,
    "provider_authentication_failed": ProviderAuthenticationFailedError,
    "provider_authorization": ProviderAuthorizationError,
    "provider_connection": ProviderConnectionError,
    "provider_protocol": ProviderProtocolError,
    "provider_response_validation": ProviderResponseValidationError,
    "provider_rate_limited": ProviderRateLimitedError,
    "provider_unsafe_operation": ProviderUnsafeOperationError,
    "provider_mutation_blocked": ProviderMutationBlockedError,
    "unsupported_capability": UnsupportedCapabilityError,
}


class FixtureErrorProvider(Provider):
    provider_id = "error-provider"
    provider_kind = "mock"
    enabled = True
    is_real_hardware = False
    risk_class = "test_fake_provider_errors"
    supported_capabilities = frozenset(DEFAULT_CAPABILITY_REGISTRY.capabilities)

    def __init__(self) -> None:
        self.requests: list[ProviderActionRequest] = []

    def execute_authorized(
        self,
        request: ProviderActionRequest,
    ) -> ProviderActionResult:
        validation = self.validate_authorized(request)
        if not validation.ok:
            return UnsupportedCapabilityError(validation.message).to_provider_result(
                request=request,
                provider_id=self.provider_id,
                provider_type=self.provider_kind,
            )
        self.requests.append(request)
        error_name = str(request.parameters.get("error_name", "provider_timeout"))
        error_type = ERROR_TYPES[error_name]
        error = error_type(detail="token must-not-leak-provider-error-secret")
        return error.to_provider_result(
            request=request,
            provider_id=self.provider_id,
            provider_type=self.provider_kind,
        )


def _runtime(provider: FixtureErrorProvider | None = None) -> ConfigRuntime:
    error_provider = provider or FixtureErrorProvider()
    provider_registry = ProviderRegistry(
        [
            ProviderEntry(
                provider_id=error_provider.provider_id,
                provider_type="mock",
                enabled=True,
                provider=error_provider,
            )
        ]
    )
    target_registry = TargetRegistry(
        provider_registry=provider_registry,
        targets=[
            TargetDefinition(
                target_id="error-target",
                provider_id=error_provider.provider_id,
                enabled=True,
                allowed_modes=frozenset(
                    {
                        ControlMode.OBSERVE,
                        ControlMode.ASSISTED,
                        ControlMode.SUPERVISED,
                        ControlMode.FULL_CONTROL,
                    }
                ),
            )
        ],
    )
    return ConfigRuntime(
        config=mock_only_config(),
        provider_registry=provider_registry,
        target_registry=target_registry,
        policy=mode_preset(ControlMode.SUPERVISED),
        audit_sink=InMemoryAuditSink(),
        approval_store=ApprovalStore(),
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[item["name"] for item in SCENARIOS])
def test_mcp_host_provider_error_lifecycle_fixtures(scenario) -> None:
    provider = FixtureErrorProvider()
    host = MCPHostCompatibilityLayer(runtime=_runtime(provider))

    result = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "error-target",
            "provider": "error-provider",
            "session_id": "provider-error-session",
            "requester_id": "provider-error-host",
            "params": {"error_name": scenario["error_name"]},
            "correlation_id": f"provider-error-{scenario['error_name']}",
        }
    )
    provider_result = result["data"]["provider_result"]
    error = provider_result["data"]["error"]

    assert result["status"] == scenario["expected_status"]
    assert result["status"] != "approval_required"
    assert provider_result["error_code"] == scenario["expected_error_code"]
    assert provider_result["retryable"] is scenario["expected_retryable"]
    assert error["approval_could_resolve"] is scenario["expected_approval_could_resolve"]
    assert provider_result["performed_on_hardware"] is False
    assert len(provider.requests) == 1
    assert "must-not-leak-provider-error-secret" not in repr(result)


def test_mcp_host_disabled_provider_fails_closed_before_execution() -> None:
    provider_registry = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="disabled-provider",
                provider_type="mock",
                enabled=False,
                provider=None,
            )
        ]
    )
    target_registry = TargetRegistry(
        provider_registry=provider_registry,
        targets=[
            TargetDefinition(
                target_id="disabled-target",
                provider_id="disabled-provider",
                enabled=True,
                allowed_modes=frozenset({ControlMode.SUPERVISED}),
            )
        ],
    )
    runtime = ConfigRuntime(
        config=mock_only_config(),
        provider_registry=provider_registry,
        target_registry=target_registry,
        policy=mode_preset(ControlMode.SUPERVISED),
        audit_sink=InMemoryAuditSink(),
        approval_store=ApprovalStore(),
    )
    host = MCPHostCompatibilityLayer(runtime=runtime)

    result = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "disabled-target",
            "session_id": "provider-error-session",
            "requester_id": "provider-error-host",
        }
    )

    assert result["status"] == "validation_error"
    assert "disabled-provider" in result["reason"]


def test_mcp_host_target_provider_mismatch_fails_closed() -> None:
    host = MCPHostCompatibilityLayer(runtime=_runtime())

    result = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "error-target",
            "provider": "other-provider",
            "session_id": "provider-error-session",
            "requester_id": "provider-error-host",
        }
    )

    assert result["status"] == "validation_error"
    assert "configured for provider error-provider" in result["reason"]
