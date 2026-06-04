import json

from agentickvm.control_plane import verify_audit_chain
from agentickvm.control_plane import LocalJSONLAuditSink
from agentickvm.mcp_sdk import (
    HostApprovalDecision,
    HostApprovalScope,
    MCPHostCompatibilityLayer,
)

from tests.contract.test_mcp_host_provider_error_lifecycle import _runtime


def _records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _event_types(path):
    return [record["event"]["event_type"] for record in _records(path)]


def _dangerous_error_call(host, error_name: str):
    return host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "error-target",
            "provider": "error-provider",
            "session_id": "approval-provider-error-session",
            "requester_id": "host-test",
            "params": {"error_name": error_name},
            "correlation_id": f"approval-provider-error-{error_name}",
        }
    )


def _approval_response(result, *, scope=HostApprovalScope.ONE_TIME):
    approval = result["approval_request"]
    return {
        "request_id": approval["id"],
        "decision": HostApprovalDecision.GRANTED.value,
        "operator_id": "operator-1",
        "scope": scope.value,
        "session_id": approval["session_id"],
        "target": approval["target"],
        "provider": approval["provider"],
        "capability": approval["capability"],
        "params_fingerprint": approval["params_fingerprint"],
    }


def test_approval_resumption_surfaces_retryable_provider_timeout(tmp_path) -> None:
    audit_path = tmp_path / "approval-provider-timeout.jsonl"
    host = MCPHostCompatibilityLayer(
        runtime=_runtime(audit_sink=LocalJSONLAuditSink(audit_path))
    )
    required = _dangerous_error_call(host, "provider_timeout")
    granted = host.submit_approval_response(_approval_response(required))

    resumed = host.resume_approved_tool(required["approval_request"]["id"])
    second = host.resume_approved_tool(required["approval_request"]["id"])
    provider_result = resumed["data"]["provider_result"]

    assert required["status"] == "approval_required"
    assert granted["status"] == "approval_granted"
    assert resumed["status"] == "provider_error"
    assert provider_result["error_code"] == "provider_timeout"
    assert provider_result["retryable"] is True
    assert second["status"] == "approval_required"
    assert "approval_consumed" in _event_types(audit_path)
    assert "provider_execution_failed" in _event_types(audit_path)
    assert verify_audit_chain(audit_path) is True


def test_session_approval_provider_error_remains_scope_bound(tmp_path) -> None:
    audit_path = tmp_path / "approval-provider-session.jsonl"
    host = MCPHostCompatibilityLayer(
        runtime=_runtime(audit_sink=LocalJSONLAuditSink(audit_path))
    )
    required = _dangerous_error_call(host, "provider_rate_limited")
    host.submit_approval_response(
        _approval_response(required, scope=HostApprovalScope.SESSION)
    )

    first = host.resume_approved_tool(required["approval_request"]["id"])
    second = host.resume_approved_tool(required["approval_request"]["id"])

    assert first["status"] == "provider_error"
    assert second["status"] == "provider_error"
    assert first["data"]["provider_result"]["error_code"] == "provider_rate_limited"
    assert second["data"]["provider_result"]["error_code"] == "provider_rate_limited"
    assert _event_types(audit_path).count("approval_consumed") == 2
    assert verify_audit_chain(audit_path) is True


def test_approval_resumption_auth_required_does_not_reveal_credentials() -> None:
    host = MCPHostCompatibilityLayer(runtime=_runtime())
    required = _dangerous_error_call(host, "provider_authentication_required")
    host.submit_approval_response(_approval_response(required))

    resumed = host.resume_approved_tool(required["approval_request"]["id"])
    provider_result = resumed["data"]["provider_result"]

    assert resumed["status"] == "provider_error"
    assert provider_result["error_code"] == "provider_authentication_required"
    assert provider_result["warnings"] == []
    assert "credential" not in provider_result["error_message"].lower()
    assert "must-not-leak" not in repr(resumed)


def test_approval_resumption_unsafe_and_mutation_errors_remain_blocked() -> None:
    for error_name, expected_code in (
        ("provider_unsafe_operation", "provider_unsafe_operation"),
        ("provider_mutation_blocked", "provider_mutation_blocked"),
    ):
        host = MCPHostCompatibilityLayer(runtime=_runtime())
        required = _dangerous_error_call(host, error_name)
        host.submit_approval_response(_approval_response(required))

        resumed = host.resume_approved_tool(required["approval_request"]["id"])
        provider_result = resumed["data"]["provider_result"]

        assert resumed["status"] == "provider_error"
        assert provider_result["error_code"] == expected_code
        assert provider_result["retryable"] is False
        assert provider_result["performed_on_hardware"] is False
