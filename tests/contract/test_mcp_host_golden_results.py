import json
from pathlib import Path

import pytest

from agentickvm.mcp_sdk import (
    HostApprovalDecision,
    MCPHostCompatibilityLayer,
)

from tests.contract.test_mcp_host_provider_error_lifecycle import _runtime

ROOT = Path(__file__).resolve().parents[2]
GOLDEN_ROOT = ROOT / "tests" / "fixtures" / "mcp_host" / "golden"
PIKVM_FIXTURE_CONFIG = ROOT / "examples" / "config" / "pikvm-observe-fixture.yaml"


def _fixture(name: str) -> dict:
    return json.loads((GOLDEN_ROOT / name).read_text(encoding="utf-8"))


def _summary(result: dict) -> dict:
    summary: dict = {
        "status": result["status"],
        "tool_name": result.get("tool_name", ""),
        "capability": result.get("capability"),
        "target": result.get("target", ""),
        "provider": result.get("provider", ""),
        "has_approval_request": "approval_request" in result,
    }
    provider_result = result.get("data", {}).get("provider_result")
    if isinstance(provider_result, dict):
        provider_summary = {
            "status": provider_result["status"],
            "provider_id": provider_result["provider_id"],
            "provider_type": provider_result["provider_type"],
            "capability": provider_result["capability"],
            "performed_on_hardware": provider_result["performed_on_hardware"],
            "error_code": provider_result["error_code"],
            "retryable": provider_result["retryable"],
        }
        screenshot = provider_result.get("data", {}).get("screenshot")
        if isinstance(screenshot, dict) and isinstance(screenshot.get("artifact"), dict):
            provider_summary["has_artifact_metadata"] = True
        summary["provider_result"] = provider_summary
    if "approval_request" in result:
        approval = result["approval_request"]
        summary["approval_request"] = {
            "target": approval["target"],
            "provider": approval["provider"],
            "capability": approval["capability"],
            "policy_decision": approval["policy_decision"],
            "scope_options": approval["scope_options"],
        }
    if result["status"] in {"denied", "validation_error"}:
        summary["reason_present"] = bool(result.get("reason"))
    return summary


def _approval_response(result: dict) -> dict:
    approval = result["approval_request"]
    return {
        "request_id": approval["id"],
        "decision": HostApprovalDecision.GRANTED.value,
        "operator_id": "operator-1",
        "scope": "one_time",
        "session_id": approval["session_id"],
        "target": approval["target"],
        "provider": approval["provider"],
        "capability": approval["capability"],
        "params_fingerprint": approval["params_fingerprint"],
    }


@pytest.mark.parametrize(
    ("fixture_name", "result_factory"),
    [
        (
            "ok-observe-mock.json",
            lambda: MCPHostCompatibilityLayer.mock_only().call_tool(
                {
                    "tool_name": "get_power_state",
                    "target": "mock-host",
                    "session_id": "golden-s1",
                    "requester_id": "golden-host",
                }
            ),
        ),
        (
            "ok-pikvm-fixture-observe.json",
            lambda: MCPHostCompatibilityLayer.from_config(
                str(PIKVM_FIXTURE_CONFIG)
            ).call_tool(
                {
                    "tool_name": "observe_screen",
                    "target": "pikvm-fixture-target",
                    "provider": "pikvm-fixture",
                    "session_id": "golden-s1",
                    "requester_id": "golden-host",
                }
            ),
        ),
        (
            "denied-hard-invariant.json",
            lambda: MCPHostCompatibilityLayer.mock_only().call_tool(
                {
                    "tool_name": "reveal_secret",
                    "target": "mock-host",
                    "session_id": "golden-s1",
                    "requester_id": "golden-host",
                }
            ),
        ),
        (
            "approval-required-dangerous.json",
            lambda: MCPHostCompatibilityLayer.mock_only().call_tool(
                {
                    "tool_name": "force_restart",
                    "target": "mock-host",
                    "session_id": "golden-s1",
                    "requester_id": "golden-host",
                    "params": {"reason": "golden approval"},
                }
            ),
        ),
        (
            "provider-error-timeout.json",
            lambda: MCPHostCompatibilityLayer(runtime=_runtime()).call_tool(
                {
                    "tool_name": "get_power_state",
                    "target": "error-target",
                    "provider": "error-provider",
                    "session_id": "golden-s1",
                    "requester_id": "golden-host",
                    "params": {"error_name": "provider_timeout"},
                }
            ),
        ),
        (
            "provider-error-auth-required.json",
            lambda: MCPHostCompatibilityLayer(runtime=_runtime()).call_tool(
                {
                    "tool_name": "get_power_state",
                    "target": "error-target",
                    "provider": "error-provider",
                    "session_id": "golden-s1",
                    "requester_id": "golden-host",
                    "params": {"error_name": "provider_authentication_required"},
                }
            ),
        ),
        (
            "validation-error-unknown-tool.json",
            lambda: MCPHostCompatibilityLayer.mock_only().call_tool(
                {
                    "tool_name": "unknown_tool",
                    "target": "mock-host",
                    "session_id": "golden-s1",
                    "requester_id": "golden-host",
                }
            ),
        ),
        (
            "validation-error-unknown-target.json",
            lambda: MCPHostCompatibilityLayer.mock_only().call_tool(
                {
                    "tool_name": "get_power_state",
                    "target": "missing-target",
                    "session_id": "golden-s1",
                    "requester_id": "golden-host",
                }
            ),
        ),
    ],
)
def test_mcp_host_golden_result_summaries(fixture_name, result_factory) -> None:
    assert _summary(result_factory()) == _fixture(fixture_name)


def test_mcp_host_golden_approval_consumed_result() -> None:
    host = MCPHostCompatibilityLayer.mock_only()
    required = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "golden-s1",
            "requester_id": "golden-host",
            "params": {"reason": "golden consumed"},
        }
    )
    host.submit_approval_response(_approval_response(required))
    resumed = host.resume_approved_tool(required["approval_request"]["id"])

    assert _summary(resumed) == _fixture("approval-consumed-ok.json")


def test_mcp_host_golden_fixtures_are_json_safe_and_non_sensitive() -> None:
    for path in GOLDEN_ROOT.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        encoded = json.dumps(payload, sort_keys=True)
        safe_encoded = encoded.replace("secrets.raw_reveal", "").replace(
            "reveal_secret",
            "",
        )

        assert json.loads(encoded) == payload
        assert "password" not in safe_encoded.lower()
        assert "token" not in safe_encoded.lower()
        assert "secret" not in safe_encoded.lower()
        assert "192.168." not in encoded
        assert "10.0." not in encoded
        assert "172.16." not in encoded
