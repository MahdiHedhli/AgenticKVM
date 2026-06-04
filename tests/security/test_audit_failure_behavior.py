from datetime import UTC, datetime

from agentickvm.config import build_runtime
from agentickvm.control_plane import InMemoryAuditSink, fingerprint_parameters
from agentickvm.mcp_sdk import (
    HostApprovalDecision,
    MCPHostCompatibilityLayer,
)


class FailingAuditSink:
    def __init__(self, message: str = "audit token must-not-leak failed") -> None:
        self.message = message
        self.events_attempted = 0

    def emit(self, event) -> None:
        self.events_attempted += 1
        raise RuntimeError(self.message)


class SwitchableAuditSink:
    def __init__(self, inner) -> None:
        self.inner = inner

    def emit(self, event) -> None:
        self.inner.emit(event)


def _mock_provider(host: MCPHostCompatibilityLayer):
    return host.adapter.runtime.provider_registry.resolve_enabled("mock")


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


def test_audit_sink_failure_blocks_read_only_execution_by_default() -> None:
    sink = FailingAuditSink()
    host = MCPHostCompatibilityLayer(runtime=build_runtime(audit_sink=sink))

    result = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "mock-host",
            "session_id": "audit-failure-s1",
            "requester_id": "audit-failure-host",
        }
    )

    assert result["status"] == "policy_error"
    assert result["reason"] == "[REDACTED]"
    assert sink.events_attempted == 1
    assert _mock_provider(host).requests == []


def test_audit_sink_failure_blocks_dangerous_execution_before_provider_call() -> None:
    sink = FailingAuditSink()
    host = MCPHostCompatibilityLayer(runtime=build_runtime(audit_sink=sink))

    result = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "audit-failure-s1",
            "requester_id": "audit-failure-host",
        }
    )

    assert result["status"] == "policy_error"
    assert result["reason"] == "[REDACTED]"
    assert _mock_provider(host).requests == []


def test_audit_sink_failure_prevents_approval_grant_creation() -> None:
    sink = SwitchableAuditSink(InMemoryAuditSink())
    host = MCPHostCompatibilityLayer(runtime=build_runtime(audit_sink=sink))
    required = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "audit-failure-s1",
            "requester_id": "audit-failure-host",
            "params": {"reason": "audit failure approval"},
        }
    )
    sink.inner = FailingAuditSink("approval password must-not-leak failed")

    submitted = host.submit_approval_response(_approval_response(required))
    store = host.adapter.runtime.approval_store
    grant = store.find_action_grant(
        capability_id="power.force_restart",
        session_id="audit-failure-s1",
        target_id="mock-host",
        provider_id="mock",
        params_fingerprint=fingerprint_parameters({"reason": "audit failure approval"}),
        now=datetime(2026, 6, 4, 3, 0, tzinfo=UTC),
    )

    assert submitted["status"] == "validation_error"
    assert submitted["reason"] == "[REDACTED]"
    assert grant is None
    assert _mock_provider(host).requests == []


def test_audit_sink_failure_blocks_resumption_when_required_audit_fails() -> None:
    sink = SwitchableAuditSink(InMemoryAuditSink())
    host = MCPHostCompatibilityLayer(runtime=build_runtime(audit_sink=sink))
    required = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "audit-failure-s1",
            "requester_id": "audit-failure-host",
            "params": {"reason": "resume audit failure"},
        }
    )
    granted = host.submit_approval_response(_approval_response(required))
    sink.inner = FailingAuditSink()

    resumed = host.resume_approved_tool(required["approval_request"]["id"])

    assert granted["status"] == "approval_granted"
    assert resumed["status"] == "policy_error"
    assert resumed["reason"] == "[REDACTED]"
    assert _mock_provider(host).requests == []
