import json
from pathlib import Path

import pytest

from agentickvm.mcp_sdk import MCPHostCompatibilityLayer

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "mcp_host"


def _load(name: str):
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _host(kind: str) -> MCPHostCompatibilityLayer:
    if kind == "mock":
        return MCPHostCompatibilityLayer.mock_only()
    if kind == "pikvm_fixture":
        return MCPHostCompatibilityLayer.from_config(
            str(ROOT / "examples" / "config" / "pikvm-observe-fixture.yaml")
        )
    raise AssertionError(f"unknown fixture host kind: {kind}")


@pytest.mark.parametrize("scenario", _load("tool-call-scenarios.json"))
def test_mcp_host_tool_call_fixture_scenarios(scenario) -> None:
    host = _host(scenario["host"])

    result = host.call_tool(scenario["request"])

    assert result["status"] == scenario["expected_status"], scenario["name"]
    assert "must-not-leak" not in repr(result)


@pytest.mark.parametrize("scenario", _load("approval-lifecycle-scenarios.json"))
def test_mcp_host_approval_lifecycle_fixture_scenarios(scenario) -> None:
    host = MCPHostCompatibilityLayer.mock_only()
    required = host.call_tool(scenario["request"])
    approval = required["approval_request"]
    response = {
        "request_id": approval["id"],
        "decision": scenario["decision"],
        "operator_id": "operator-1",
        "scope": scenario["scope"],
        "session_id": approval["session_id"],
        "target": scenario.get("override_target", approval["target"]),
        "provider": approval["provider"],
        "capability": approval["capability"],
        "params_fingerprint": approval["params_fingerprint"],
    }

    submitted = host.submit_approval_response(response)
    resumed = host.resume_approved_tool(approval["id"])

    assert required["status"] == "approval_required"
    assert submitted["status"] == scenario["expected_submit_status"], scenario["name"]
    assert resumed["status"] == scenario["expected_resume_status"], scenario["name"]
    if "expected_second_resume_status" in scenario:
        second = host.resume_approved_tool(approval["id"])
        assert second["status"] == scenario["expected_second_resume_status"]
