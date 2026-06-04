import json
from pathlib import Path

import pytest

from agentickvm.config import build_runtime
from agentickvm.control_plane import (
    InMemoryAuditSink,
    LocalJSONLAuditSink,
    create_audit_checkpoint,
    export_audit_log,
    verify_audit_checkpoint,
    verify_audit_chain,
    verify_audit_export,
)
from agentickvm.mcp_sdk import HostApprovalDecision, MCPHostCompatibilityLayer

from tests.contract.test_mcp_host_provider_error_lifecycle import _runtime

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = json.loads(
    (
        ROOT
        / "tests"
        / "fixtures"
        / "mcp_host"
        / "audit"
        / "conformance-scenarios.json"
    ).read_text(encoding="utf-8")
)
PIKVM_FIXTURE_CONFIG = ROOT / "examples" / "config" / "pikvm-observe-fixture.yaml"


class FailingAuditSink:
    def emit(self, event) -> None:
        raise RuntimeError("audit token must-not-leak failed")


class SwitchableAuditSink:
    def __init__(self, inner) -> None:
        self.inner = inner

    def emit(self, event) -> None:
        self.inner.emit(event)


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _event_types(path: Path) -> list[str]:
    return [record["event"]["event_type"] for record in _records(path)]


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


def _run_flow(flow: str, audit_path: Path) -> dict:
    if flow == "ok":
        return MCPHostCompatibilityLayer.mock_only(audit_path=audit_path).call_tool(
            {
                "tool_name": "get_power_state",
                "target": "mock-host",
                "session_id": "audit-conformance-s1",
                "requester_id": "audit-conformance-host",
            }
        )
    if flow == "denied":
        return MCPHostCompatibilityLayer.mock_only(audit_path=audit_path).call_tool(
            {
                "tool_name": "reveal_secret",
                "target": "mock-host",
                "session_id": "audit-conformance-s1",
                "requester_id": "audit-conformance-host",
            }
        )
    if flow == "approval_required":
        return MCPHostCompatibilityLayer.mock_only(audit_path=audit_path).call_tool(
            {
                "tool_name": "force_restart",
                "target": "mock-host",
                "session_id": "audit-conformance-s1",
                "requester_id": "audit-conformance-host",
            }
        )
    if flow == "approval_consumed":
        host = MCPHostCompatibilityLayer.mock_only(audit_path=audit_path)
        required = host.call_tool(
            {
                "tool_name": "force_restart",
                "target": "mock-host",
                "session_id": "audit-conformance-s1",
                "requester_id": "audit-conformance-host",
            }
        )
        host.submit_approval_response(_approval_response(required))
        return host.resume_approved_tool(required["approval_request"]["id"])
    if flow == "provider_error":
        return MCPHostCompatibilityLayer(
            runtime=_runtime(audit_sink=LocalJSONLAuditSink(audit_path))
        ).call_tool(
            {
                "tool_name": "get_power_state",
                "target": "error-target",
                "provider": "error-provider",
                "session_id": "audit-conformance-s1",
                "requester_id": "audit-conformance-host",
                "params": {"error_name": "provider_timeout"},
            }
        )
    if flow == "artifact":
        return MCPHostCompatibilityLayer.from_config(
            str(PIKVM_FIXTURE_CONFIG),
            audit_path=audit_path,
        ).call_tool(
            {
                "tool_name": "observe_screen",
                "target": "pikvm-fixture-target",
                "provider": "pikvm-fixture",
                "session_id": "audit-conformance-s1",
                "requester_id": "audit-conformance-host",
            }
        )
    raise AssertionError(f"unknown fixture flow {flow}")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[item["name"] for item in SCENARIOS])
def test_mcp_host_audit_conformance_fixture_scenarios(tmp_path, scenario) -> None:
    audit_path = tmp_path / f"{scenario['flow']}.jsonl"

    result = _run_flow(scenario["flow"], audit_path)
    event_types = _event_types(audit_path)
    encoded = audit_path.read_text(encoding="utf-8")

    assert result["status"] == scenario["expected_status"]
    for event_type in scenario["expected_events"]:
        assert event_type in event_types
    assert verify_audit_chain(audit_path) is True
    assert "must-not-leak" not in encoded
    assert "screenshot_bytes" not in encoded
    assert "raw_image" not in encoded


def test_mcp_host_audit_checkpoint_and_export_conformance(tmp_path) -> None:
    audit_path = tmp_path / "checkpoint-export.jsonl"
    result = _run_flow("approval_consumed", audit_path)

    checkpoint = create_audit_checkpoint(
        audit_path,
        audit_log_id="host-conformance",
    )
    checkpoint_verification = verify_audit_checkpoint(audit_path, checkpoint)
    bundle = export_audit_log(
        audit_path,
        audit_log_id="host-conformance",
        checkpoint=checkpoint,
    )
    export_verification = verify_audit_export(bundle)

    assert result["status"] == "ok"
    assert checkpoint_verification.ok is True
    assert export_verification.ok is True
    assert export_verification.checkpoint_verified is True


def test_mcp_host_audit_failure_conformance_blocks_provider_execution() -> None:
    sink = SwitchableAuditSink(InMemoryAuditSink())
    host = MCPHostCompatibilityLayer(runtime=build_runtime(audit_sink=sink))
    required = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "audit-conformance-s1",
            "requester_id": "audit-conformance-host",
        }
    )
    host.submit_approval_response(_approval_response(required))
    sink.inner = FailingAuditSink()

    result = host.resume_approved_tool(required["approval_request"]["id"])
    provider = host.adapter.runtime.provider_registry.resolve_enabled("mock")

    assert result["status"] == "policy_error"
    assert result["reason"] == "[REDACTED]"
    assert provider.requests == []
