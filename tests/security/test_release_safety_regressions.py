import inspect
from pathlib import Path

import pytest

from agentickvm.config import load_config
from agentickvm.control_plane import (
    Actor,
    ActorType,
    CapabilityRequest,
    ControlMode,
    InMemoryAuditSink,
    TargetDefinition,
    TargetRegistry,
    TargetRegistryError,
    mode_preset,
)
from agentickvm.control_plane import ControlPlane, ControlPlaneStatus
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest
from agentickvm.mcp import router as mcp_router_module
from agentickvm.mcp_sdk import adapter as sdk_adapter_module
from agentickvm.mcp_sdk import host as host_module
from agentickvm.providers import (
    MockProvider,
    PiKVMProviderPlaceholder,
    ProviderEntry,
    ProviderRegistry,
    ProviderRegistryError,
    RedfishProviderPlaceholder,
)


ROOT = Path(__file__).resolve().parents[2]


def _provider_registry() -> ProviderRegistry:
    return ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                provider=MockProvider(),
            )
        ]
    )


def _target_registry(provider_registry: ProviderRegistry) -> TargetRegistry:
    return TargetRegistry(
        provider_registry=provider_registry,
        targets=[TargetDefinition(target_id="mock-host", provider_id="mock")],
    )


def _router(
    *,
    provider_registry: ProviderRegistry | None = None,
    target_registry: TargetRegistry | None = None,
    mode: ControlMode = ControlMode.FULL_CONTROL,
) -> tuple[MCPRouter, InMemoryAuditSink]:
    providers = provider_registry or _provider_registry()
    targets = target_registry or _target_registry(providers)
    sink = InMemoryAuditSink()
    return (
        MCPRouter(
            provider_registry=providers,
            target_registry=targets,
            policy=mode_preset(mode),
            audit_sink=sink,
        ),
        sink,
    )


def _mcp_request(
    tool_name: str,
    *,
    target: str = "mock-host",
    provider: str | None = "mock",
    **params: object,
) -> MCPToolRequest:
    return MCPToolRequest(
        tool_name=tool_name,
        target=target,
        provider=provider,
        session_id="release-safety-session",
        requester_id="release-safety-agent",
        params=params,
    )


def _capability_request(capability_id: str) -> CapabilityRequest:
    return CapabilityRequest(
        capability_id=capability_id,
        target_id="mock-host",
        session_id="release-safety-session",
        correlation_id=f"release-safety:{capability_id}",
        requester=Actor(type=ActorType.AGENT, id="release-safety-agent"),
        intended_effect=f"release regression check for {capability_id}",
    )


def test_unknown_capability_fails_closed_before_provider_execution() -> None:
    provider = MockProvider()
    sink = InMemoryAuditSink()
    control_plane = ControlPlane(
        policy=mode_preset(ControlMode.FULL_CONTROL),
        provider=provider,
        audit_sink=sink,
    )

    result = control_plane.handle(_capability_request("unknown.release_capability"))

    assert result.status == ControlPlaneStatus.DENIED
    assert result.message == "unknown capability"
    assert provider.requests == []
    assert any(event.event_type.value == "capability_unknown_denied" for event in sink.events)


def test_unknown_provider_and_target_fail_closed() -> None:
    providers = _provider_registry()
    targets = _target_registry(providers)

    with pytest.raises(ProviderRegistryError, match="Unknown provider id"):
        providers.resolve_enabled("missing-provider")

    with pytest.raises(TargetRegistryError, match="Unknown target id"):
        targets.resolve_enabled("missing-target")


def test_disabled_provider_and_target_fail_closed() -> None:
    disabled_providers = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                enabled=False,
                provider=None,
            )
        ]
    )
    disabled_provider_targets = TargetRegistry(
        provider_registry=disabled_providers,
        targets=[TargetDefinition(target_id="mock-host", provider_id="mock")],
    )

    with pytest.raises(ProviderRegistryError, match="disabled"):
        disabled_providers.resolve_enabled("mock")
    with pytest.raises(TargetRegistryError, match="non-executable provider"):
        disabled_provider_targets.resolve_enabled("mock-host")

    providers = _provider_registry()
    disabled_targets = TargetRegistry(
        provider_registry=providers,
        targets=[
            TargetDefinition(
                target_id="mock-host",
                provider_id="mock",
                enabled=False,
            )
        ],
    )

    with pytest.raises(TargetRegistryError, match="disabled"):
        disabled_targets.resolve_enabled("mock-host")


@pytest.mark.parametrize(
    ("tool_name", "capability", "expected_reason"),
    [
        ("modify_policy", "session.modify_policy", "hard invariant"),
        ("reveal_secret", "secrets.raw_reveal", "missing required credential scope"),
    ],
)
def test_hard_invariant_mcp_tools_remain_denied(
    tool_name: str,
    capability: str,
    expected_reason: str,
) -> None:
    router, sink = _router(mode=ControlMode.FULL_CONTROL)

    result = router.handle_tool_request(_mcp_request(tool_name))

    assert result.status == MCPResultStatus.DENIED
    assert result.capability == capability
    assert result.reason == expected_reason
    assert any(event.event_type.value == "policy_decision" for event in sink.events)


@pytest.mark.parametrize(
    "capability_id",
    [
        "session.disable_audit",
        "session.disable_emergency_stop",
    ],
)
def test_control_plane_cannot_disable_audit_or_emergency_stop(
    capability_id: str,
) -> None:
    provider = MockProvider()
    control_plane = ControlPlane(
        policy=mode_preset(ControlMode.FULL_CONTROL),
        provider=provider,
        audit_sink=InMemoryAuditSink(),
    )

    result = control_plane.handle(_capability_request(capability_id))

    assert result.status == ControlPlaneStatus.DENIED
    assert result.message == "hard invariant"
    assert provider.requests == []


def test_live_provider_placeholders_remain_disabled_and_non_executable() -> None:
    for provider in (PiKVMProviderPlaceholder(), RedfishProviderPlaceholder()):
        status = provider.status()

        assert status.enabled is False
        assert status.is_real_hardware is True
        assert provider.supports("power.force_restart") is False


@pytest.mark.parametrize("provider_type", ["pikvm", "redfish"])
def test_live_provider_config_is_rejected_by_default(
    provider_type: str,
    tmp_path: Path,
) -> None:
    config_path = tmp_path / f"{provider_type}-enabled.json"
    config_path.write_text(
        """
{
  "providers": [
    {"id": "live-placeholder", "type": "%s", "enabled": true}
  ],
  "targets": []
}
"""
        % provider_type,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not executable|live provider config"):
        load_config(config_path)


def test_mcp_host_adapter_and_router_keep_provider_execution_behind_control_plane() -> None:
    for obj in (
        host_module.MCPHostCompatibilityLayer,
        sdk_adapter_module.MCPSDKAdapter,
        mcp_router_module.MCPRouter,
    ):
        source = inspect.getsource(obj)
        assert "execute_authorized" not in source

    adapter_source = inspect.getsource(sdk_adapter_module.MCPSDKAdapter)
    router_source = inspect.getsource(mcp_router_module.MCPRouter)

    assert "MCPRouter" in adapter_source
    assert "control_plane_factory" in router_source


def test_mcp_unknown_target_and_disabled_provider_return_validation_errors() -> None:
    router, _sink = _router()

    unknown_target = router.handle_tool_request(
        _mcp_request("get_status", target="missing-target", provider=None)
    )

    assert unknown_target.status == MCPResultStatus.VALIDATION_ERROR
    assert "Unknown target id" in unknown_target.reason

    disabled_providers = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                enabled=False,
                provider=None,
            )
        ]
    )
    disabled_targets = TargetRegistry(
        provider_registry=disabled_providers,
        targets=[TargetDefinition(target_id="mock-host", provider_id="mock")],
    )
    disabled_router, _sink = _router(
        provider_registry=disabled_providers,
        target_registry=disabled_targets,
    )

    disabled_result = disabled_router.handle_tool_request(_mcp_request("get_status"))

    assert disabled_result.status == MCPResultStatus.VALIDATION_ERROR
    assert "non-executable provider" in disabled_result.reason


def test_public_site_and_metadata_do_not_claim_live_or_trial_support() -> None:
    site = (ROOT / "site" / "index.html").read_text(encoding="utf-8").lower()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()

    forbidden_site_claims = (
        "production ready",
        "fully supports live pikvm",
        "fully supports live redfish",
        "supports rdp today",
        "supports vnc today",
        "supports rustdesk today",
        "supports meshcentral today",
        "autonomous production recovery",
        "zero risk",
    )
    for claim in forbidden_site_claims:
        assert claim not in site

    assert "mcp==1.27.2" not in pyproject
    assert "safety guardrails built in" in site
    assert "future roadmap" in site


def test_workflows_remain_secret_free_and_mock_only() -> None:
    workflow_dir = ROOT / ".github" / "workflows"
    workflow_text = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in sorted(workflow_dir.glob("*.yml"))
    )

    assert "secrets." not in workflow_text
    assert "mcp==1.27.2" not in workflow_text
    assert "uv run --with" not in workflow_text
    for forbidden in (
        "pikvm",
        "redfish",
        "rustdesk",
        "meshcentral",
        "supermicro",
        "proxmox",
        "provider smoke",
        "live smoke",
    ):
        assert forbidden not in workflow_text
