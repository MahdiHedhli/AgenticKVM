"""End-to-end observe + fail-closed routine through the MCP router.

Covers the safe everyday path (observe runs and is redacted) and the fail-closed
boundary (unknown tools, provider mismatch, and dangerous actuation in an
observe-only policy never reach hardware). Mock-only: fixture transport, no
network, no hardware.
"""

from __future__ import annotations

from agentickvm.config import build_runtime, config_from_mapping
from agentickvm.mcp import MCPResultStatus, MCPRouter, MCPToolRequest

OBSERVE_PIKVM_CONFIG = {
    "version": "0.1",
    "providers": [
        {
            "id": "pikvm-fixture",
            "type": "pikvm",
            "enabled": True,
            "description": "Fixture-backed PiKVM observe provider for offline tests",
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
            "labels": ["pikvm", "observe-only", "fixture"],
            "risk_tier": "low",
            "allowed_modes": ["Observe"],
            "metadata": {"description": "offline observe-only fixture target"},
        }
    ],
    "default_policy": {"mode": "Observe"},
}


def _router():
    runtime = build_runtime(config_from_mapping(OBSERVE_PIKVM_CONFIG))
    router = MCPRouter(
        provider_registry=runtime.provider_registry,
        target_registry=runtime.target_registry,
        policy=runtime.policy,
        audit_sink=runtime.audit_sink,
    )
    provider = runtime.provider_registry.resolve_enabled("pikvm-fixture")
    return router, provider


def _request(tool_name: str, *, provider: str = "pikvm-fixture") -> MCPToolRequest:
    return MCPToolRequest(
        tool_name=tool_name,
        target="pikvm-fixture-target",
        session_id="s1",
        requester_id="agent-1",
        provider=provider,
        correlation_id=f"observe-routine-{tool_name}",
    )


def test_observe_routine_runs_and_redacts() -> None:
    router, provider = _router()

    screen = router.handle_tool_request(_request("observe_screen"))
    power = router.handle_tool_request(_request("get_power_state"))

    assert screen.status == MCPResultStatus.OK
    screen_data = screen.data["provider_result"]["data"]
    assert screen_data["screen"]["content"] == "[REDACTED]"
    assert screen_data["screenshot"]["raw_bytes_included"] is False
    assert "keychain://" not in repr(screen.to_dict())

    assert power.status == MCPResultStatus.OK
    assert power.data["provider_result"]["data"]["power_state"] == "on"
    # Observe never claims a hardware action.
    assert power.data["provider_result"]["performed_on_hardware"] is False


def test_actuation_denied_in_observe_only_policy() -> None:
    router, provider = _router()

    for tool in ("power_on", "power_reset", "type_text", "mouse_click"):
        result = router.handle_tool_request(_request(tool))
        assert result.status == MCPResultStatus.DENIED, tool

    assert provider.requests == []


def test_unknown_tool_fails_closed_as_validation_error() -> None:
    router, provider = _router()

    result = router.handle_tool_request(_request("definitely_not_a_tool"))

    assert result.status == MCPResultStatus.VALIDATION_ERROR
    assert provider.requests == []


def test_provider_mismatch_fails_closed() -> None:
    router, provider = _router()

    result = router.handle_tool_request(_request("observe_screen", provider="other-provider"))

    assert result.status == MCPResultStatus.VALIDATION_ERROR
    assert provider.requests == []
