from __future__ import annotations

from agentickvm.control_plane import (
    ACTClearanceVerifier,
    ControlMode,
    MockACTClient,
    MockACTProofVerifier,
    mode_preset,
)
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest
from agentickvm.providers import MockProvider, ProviderEntry, ProviderRegistry
from agentickvm.control_plane.targets import TargetDefinition, TargetRegistry


def _router() -> MCPRouter:
    providers = ProviderRegistry(
        [ProviderEntry(provider_id="mock", provider_type="mock", provider=MockProvider())]
    )
    targets = TargetRegistry(
        provider_registry=providers,
        targets=[TargetDefinition(target_id="mock-host", provider_id="mock")],
    )
    return MCPRouter(
        provider_registry=providers,
        target_registry=targets,
        policy=mode_preset(ControlMode.SUPERVISED),
        clearance_client=MockACTClient(),
        clearance_verifier=ACTClearanceVerifier(
            tower_id="mock-act",
            proof_verifier=MockACTProofVerifier(),
            test_mode=True,
        ),
    )


def test_clearance_required_result_contains_operator_contract() -> None:
    result = _router().handle_tool_request(
        MCPToolRequest(
            tool_name="force_restart",
            target="mock-host",
            provider="mock",
            session_id="session-1",
            requester_id="agent",
            params={"force": True, "password": "secret-value"},
        )
    )

    payload = result.to_dict()
    clearance = payload["data"]["clearance_request"]

    assert result.status == MCPResultStatus.CLEARANCE_REQUIRED
    assert payload["status"] == "clearance_required"
    assert clearance["short_code"]
    assert clearance["operator_message"]
    assert ".." not in clearance["operator_message"]
    assert "Surface this code to the operator" in clearance["operator_message"]
    assert "retry with identical parameters" in payload["data"]["retry_guidance"]
    assert clearance["risk_summary"]["risk_family"] == "power"
    assert payload["data"]["params_preview"]["password"] == "[REDACTED]"
    assert "params.password" in payload["redactions"]
    assert "chat approval" not in clearance["operator_message"].lower()
