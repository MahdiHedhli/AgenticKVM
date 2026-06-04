import json

from agentickvm.mcp_sdk import (
    HostApprovalResult,
    HostApprovalResultStatus,
    HostError,
    HostResultStatus,
    HostToolResult,
    MCPHostCompatibilityLayer,
)


def _round_trip(payload):
    return json.loads(json.dumps(payload, sort_keys=True))


def test_host_tool_result_statuses_round_trip_json_safely() -> None:
    for status in HostResultStatus:
        result = HostToolResult(
            status=status,
            tool_name="test_tool",
            capability="runtime.noop",
            target="mock-host",
            provider="mock",
            reason="safe reason",
            data={"detail": "safe"},
        ).to_dict()

        assert _round_trip(result)["status"] == status.value


def test_host_error_statuses_round_trip_json_safely() -> None:
    for status in (
        HostResultStatus.VALIDATION_ERROR,
        HostResultStatus.PROVIDER_ERROR,
        HostResultStatus.POLICY_ERROR,
    ):
        error = HostError(
            status=status,
            reason="secret must-not-leak-host-secret",
            tool_name="test_tool",
            details={"password": "must-not-leak-host-secret"},
        ).to_dict()

        round_tripped = _round_trip(error)

        assert round_tripped["status"] == status.value
        assert "must-not-leak-host-secret" not in repr(round_tripped)
        assert round_tripped["reason"] == "[REDACTED]"


def test_host_approval_result_statuses_round_trip_json_safely() -> None:
    for status in HostApprovalResultStatus:
        result = HostApprovalResult(
            status=status,
            request_id="approval-1",
            reason="token must-not-leak-host-secret",
            grant={"credential_ref": "ref:test-only"},
        ).to_dict()

        round_tripped = _round_trip(result)

        assert round_tripped["status"] == status.value
        assert "must-not-leak-host-secret" not in repr(round_tripped)
        assert round_tripped["reason"] == "[REDACTED]"
        assert round_tripped["grant"]["credential_ref"] == "[REDACTED]"


def test_host_malformed_request_returns_redacted_structured_error() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    result = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "s1",
            "requester_id": "host-test",
            "params": {"password": "must-not-leak-host-secret"},
            "approval_context": ["not", "an", "object"],
        }
    )

    assert result["status"] == "validation_error"
    assert "must-not-leak-host-secret" not in repr(result)
    _round_trip(result)


def test_host_serializes_provider_policy_and_validation_errors_safely() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    provider_error = host.serialize_error(
        RuntimeError("provider token must-not-leak-host-secret failed"),
        status=HostResultStatus.PROVIDER_ERROR,
        tool_name="observe_screen",
    )
    policy_error = host.serialize_error(
        RuntimeError("policy secret must-not-leak-host-secret failed"),
        status=HostResultStatus.POLICY_ERROR,
        tool_name="modify_policy",
    )
    validation_error = host.serialize_error(
        RuntimeError("validation password must-not-leak-host-secret failed"),
        status=HostResultStatus.VALIDATION_ERROR,
        tool_name="unknown_tool",
    )

    for payload in (provider_error, policy_error, validation_error):
        assert "must-not-leak-host-secret" not in repr(payload)
        assert payload["reason"] == "[REDACTED]"
        _round_trip(payload)


def test_host_approval_submission_malformed_response_is_structured() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    result = host.submit_approval_response(
        {
            "request_id": "approval-1",
            "decision": "granted",
            "operator_id": "operator-1",
            "reason": "token must-not-leak-host-secret",
            "scope": "bad-scope",
        }
    )

    assert result["status"] == "validation_error"
    assert "must-not-leak-host-secret" not in repr(result)
    _round_trip(result)
