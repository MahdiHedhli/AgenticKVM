"""End-to-end mock-cleared actuation routine through the MCP router.

This is the agent-facing process: an agent asks for a dangerous PiKVM actuation
through the MCP tool surface, the control plane requires ACT clearance, and the
fixture actuation runs only after a mock-cleared response -- never on hardware.
Pending and denied clearances fail closed, HID text is redacted, and the
local_terminal opt-out routes to the local broker instead of ACT.

Everything here is mock-only: a fixture PiKVM transport, a mock ACT client, and
no live network or hardware.
"""

from __future__ import annotations

from agentickvm.config import build_runtime, config_from_mapping
from agentickvm.control_plane import (
    ACTClearanceVerifier,
    AuthChannel,
    ClearanceStatus,
    MockACTClient,
    MockACTProofVerifier,
)
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest

SUPERVISED_PIKVM_CONFIG = {
    "version": "0.1",
    "providers": [
        {
            "id": "pikvm-fixture",
            "type": "pikvm",
            "enabled": True,
            "description": "Fixture-backed PiKVM provider for offline actuation tests",
            "metadata": {"fixture_mode": True, "live_mode": False, "transport": "fake"},
        }
    ],
    "targets": [
        {
            "id": "pikvm-fixture-target",
            "provider": "pikvm-fixture",
            "enabled": True,
            "name": "PiKVM Fixture Target",
            "environment": "fixture",
            "labels": ["pikvm", "fixture"],
            "risk_tier": "low",
            "allowed_modes": ["Observe", "Supervised"],
            "metadata": {"description": "offline fixture actuation target"},
        }
    ],
    "default_policy": {"mode": "Supervised"},
}


def _verifier() -> ACTClearanceVerifier:
    return ACTClearanceVerifier(
        tower_id="mock-act",
        proof_verifier=MockACTProofVerifier(),
        test_mode=True,
    )


def _router(*, act_client: MockACTClient, auth_channel=AuthChannel.MOBILE_SIGNED):
    runtime = build_runtime(config_from_mapping(SUPERVISED_PIKVM_CONFIG))
    router = MCPRouter(
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=runtime.policy,
        audit_sink=runtime.audit_sink,
        clearance_client=act_client,
        clearance_verifier=_verifier(),
        auth_channel=auth_channel,
    )
    provider = runtime.provider_registry.resolve_enabled("pikvm-fixture")
    return router, provider


def _tool_request(tool_name: str, **params) -> MCPToolRequest:
    return MCPToolRequest(
        tool_name=tool_name,
        target="pikvm-fixture-target",
        session_id="s1",
        requester_id="agent-1",
        provider="pikvm-fixture",
        correlation_id=f"routine-{tool_name}",
        params=params,
    )


def test_mock_cleared_power_actuation_runs_on_fixture_without_hardware() -> None:
    router, provider = _router(act_client=MockACTClient(default_status=ClearanceStatus.CLEARED))

    result = router.handle_tool_request(_tool_request("power_on"))

    assert result.status == MCPResultStatus.OK
    assert result.capability == "power.on"
    provider_result = result.data["provider_result"]
    assert provider_result["performed_on_hardware"] is False
    assert provider_result["data"]["performed"] is False
    assert provider_result["data"]["fixture"] is True
    assert provider.requests[-1].capability == "power.on"


def test_pending_clearance_blocks_actuation_before_provider() -> None:
    router, provider = _router(act_client=MockACTClient())  # default pending

    result = router.handle_tool_request(_tool_request("power_reset"))

    assert result.status == MCPResultStatus.CLEARANCE_REQUIRED
    assert result.data["clearance_request"]["short_code"]
    assert provider.requests == []


def test_denied_clearance_fails_closed() -> None:
    router, provider = _router(act_client=MockACTClient(default_status=ClearanceStatus.DENIED))

    result = router.handle_tool_request(_tool_request("power_off"))

    assert result.status == MCPResultStatus.DENIED
    assert provider.requests == []


def test_mock_cleared_keyboard_actuation_redacts_typed_text() -> None:
    router, _ = _router(act_client=MockACTClient(default_status=ClearanceStatus.CLEARED))
    secret = "hunter2-not-a-real-password"

    result = router.handle_tool_request(_tool_request("type_text", text=secret))

    assert result.status == MCPResultStatus.OK
    assert result.capability == "input.keyboard_type"
    assert secret not in repr(result.to_dict())
    assert result.data["provider_result"]["data"]["parameters"]["text"] == "[REDACTED]"


def test_local_terminal_opt_out_routes_actuation_to_local_broker() -> None:
    router, provider = _router(
        act_client=MockACTClient(default_status=ClearanceStatus.CLEARED),
        auth_channel=AuthChannel.LOCAL_TERMINAL,
    )

    result = router.handle_tool_request(_tool_request("power_on"))

    # local_terminal bypasses ACT and uses the local broker, which has no grant.
    assert result.status == MCPResultStatus.APPROVAL_REQUIRED
    assert provider.requests == []
