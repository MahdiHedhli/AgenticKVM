import json
from pathlib import Path
from datetime import datetime, timedelta

from agentickvm.control_plane import verify_audit_chain
from agentickvm.mcp_sdk import (
    HostApprovalDecision,
    MCPHostCompatibilityLayer,
)

ROOT = Path(__file__).resolve().parents[2]


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _event_types(path: Path) -> list[str]:
    return [record["event"]["event_type"] for record in _records(path)]


def _approval_response(result, *, decision=HostApprovalDecision.GRANTED, **overrides):
    approval = result["approval_request"]
    return {
        "request_id": approval["id"],
        "decision": decision.value,
        "operator_id": "operator-1",
        "scope": "one_time",
        "decided_at": overrides.pop("decided_at", None),
        "session_id": approval["session_id"],
        "target": approval["target"],
        "provider": approval["provider"],
        "capability": approval["capability"],
        "params_fingerprint": approval["params_fingerprint"],
        **overrides,
    }


def test_host_ok_call_writes_hash_chained_audit_jsonl(tmp_path) -> None:
    audit_path = tmp_path / "audit" / "host-ok.jsonl"
    host = MCPHostCompatibilityLayer.mock_only(audit_path=audit_path)

    result = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "mock-host",
            "session_id": "host-audit-s1",
            "requester_id": "host-test",
            "correlation_id": "host-audit-ok",
        }
    )

    assert result["status"] == "ok"
    assert audit_path.exists()
    assert sorted(path.name for path in tmp_path.iterdir()) == ["audit"]
    assert verify_audit_chain(audit_path) is True
    assert "provider_execution_completed" in _event_types(audit_path)
    assert _records(audit_path)[0]["previous_hash"] is None


def test_host_denied_and_approval_required_actions_are_audited(tmp_path) -> None:
    audit_path = tmp_path / "host-denied-approval.jsonl"
    host = MCPHostCompatibilityLayer.mock_only(audit_path=audit_path)

    denied = host.call_tool(
        {
            "tool_name": "reveal_secret",
            "target": "mock-host",
            "session_id": "host-audit-s1",
            "requester_id": "host-test",
        }
    )
    approval_required = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "host-audit-s1",
            "requester_id": "host-test",
        }
    )

    event_types = _event_types(audit_path)

    assert denied["status"] == "denied"
    assert approval_required["status"] == "approval_required"
    assert "approval_requested" in event_types
    assert event_types.count("result_returned") >= 2
    assert verify_audit_chain(audit_path) is True


def test_host_approval_lifecycle_and_consumption_are_audited(tmp_path) -> None:
    audit_path = tmp_path / "host-approval-lifecycle.jsonl"
    host = MCPHostCompatibilityLayer.mock_only(audit_path=audit_path)
    required = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "host-audit-s1",
            "requester_id": "host-test",
            "params": {"password": "must-not-leak-host-secret"},
            "correlation_id": "host-audit-approval",
        }
    )
    granted = host.submit_approval_response(_approval_response(required))
    resumed = host.resume_approved_tool(required["approval_request"]["id"])

    event_types = _event_types(audit_path)
    content = audit_path.read_text(encoding="utf-8")

    assert granted["status"] == "approval_granted"
    assert resumed["status"] == "ok"
    assert "approval_requested" in event_types
    assert "approval_granted" in event_types
    assert "approval_consumed" in event_types
    assert "provider_execution_completed" in event_types
    assert "must-not-leak-host-secret" not in content
    assert "[REDACTED]" in content
    assert verify_audit_chain(audit_path) is True


def test_host_denied_and_expired_approval_responses_are_audited(tmp_path) -> None:
    audit_path = tmp_path / "host-approval-denied-expired.jsonl"
    host = MCPHostCompatibilityLayer.mock_only(audit_path=audit_path)
    denied_required = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "host-audit-s1",
            "requester_id": "host-test",
            "correlation_id": "host-audit-denied",
        }
    )
    denied = host.submit_approval_response(
        _approval_response(denied_required, decision=HostApprovalDecision.DENIED)
    )
    expired_required = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "host-audit-s1",
            "requester_id": "host-test",
            "correlation_id": "host-audit-expired",
        }
    )
    expired_at = datetime.fromisoformat(
        expired_required["approval_request"]["expires_at"]
    )
    expired = host.submit_approval_response(
        _approval_response(
            expired_required,
            decided_at=(expired_at + timedelta(seconds=1)).isoformat(),
        )
    )

    event_types = _event_types(audit_path)

    assert denied["status"] == "approval_denied"
    assert expired["status"] == "approval_expired"
    assert "approval_denied" in event_types
    assert "approval_expired" in event_types
    assert verify_audit_chain(audit_path) is True


def test_host_audit_hash_chain_detects_tampering(tmp_path) -> None:
    audit_path = tmp_path / "host-tamper.jsonl"
    host = MCPHostCompatibilityLayer.mock_only(audit_path=audit_path)
    host.call_tool(
        {
            "tool_name": "get_status",
            "target": "mock-host",
            "session_id": "host-audit-s1",
            "requester_id": "host-test",
        }
    )

    tampered = audit_path.read_text(encoding="utf-8").replace("completed", "changed")
    audit_path.write_text(tampered, encoding="utf-8")

    assert verify_audit_chain(audit_path) is False


def test_host_audit_hash_chain_detects_middle_event_deletion(tmp_path) -> None:
    audit_path = tmp_path / "host-deletion-tamper.jsonl"
    host = MCPHostCompatibilityLayer.mock_only(audit_path=audit_path)
    host.call_tool(
        {
            "tool_name": "get_status",
            "target": "mock-host",
            "session_id": "host-audit-s1",
            "requester_id": "host-test",
        }
    )
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 3

    audit_path.write_text("\n".join([lines[0], *lines[2:]]) + "\n", encoding="utf-8")

    assert verify_audit_chain(audit_path) is False


def test_host_audit_hash_chain_detects_event_reordering(tmp_path) -> None:
    audit_path = tmp_path / "host-reorder-tamper.jsonl"
    host = MCPHostCompatibilityLayer.mock_only(audit_path=audit_path)
    host.call_tool(
        {
            "tool_name": "get_status",
            "target": "mock-host",
            "session_id": "host-audit-s1",
            "requester_id": "host-test",
        }
    )
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) > 3
    lines[1], lines[2] = lines[2], lines[1]

    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert verify_audit_chain(audit_path) is False


def test_host_provider_error_audit_preserves_correlation(tmp_path) -> None:
    audit_path = tmp_path / "host-provider-error.jsonl"
    host = MCPHostCompatibilityLayer.from_config(
        str(ROOT / "examples" / "config" / "pikvm-observe-fixture.yaml"),
        audit_path=audit_path,
    )

    result = host.call_tool(
        {
            "tool_name": "get_sensors",
            "target": "pikvm-fixture-target",
            "provider": "pikvm-fixture",
            "session_id": "host-audit-s1",
            "requester_id": "host-test",
            "correlation_id": "host-provider-error-corr",
        }
    )
    records = _records(audit_path)

    assert result["status"] == "provider_error"
    assert "provider_execution_failed" in _event_types(audit_path)
    assert {record["event"]["correlation_id"] for record in records} == {
        "host-provider-error-corr"
    }
    assert verify_audit_chain(audit_path) is True


def test_host_audit_does_not_write_raw_screenshot_bytes(tmp_path) -> None:
    audit_path = tmp_path / "host-screenshot.jsonl"
    host = MCPHostCompatibilityLayer.from_config(
        str(ROOT / "examples" / "config" / "pikvm-observe-fixture.yaml"),
        audit_path=audit_path,
    )

    result = host.call_tool(
        {
            "tool_name": "observe_screen",
            "target": "pikvm-fixture-target",
            "provider": "pikvm-fixture",
            "session_id": "host-audit-s1",
            "requester_id": "host-test",
        }
    )
    content = audit_path.read_text(encoding="utf-8")

    assert result["status"] == "ok"
    assert "raw_bytes_included" in repr(result)
    assert "screenshot_bytes" not in content
    assert "raw_image" not in content
    assert verify_audit_chain(audit_path) is True
