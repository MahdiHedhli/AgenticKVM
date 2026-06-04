import pytest

from agentickvm.mcp_sdk import (
    HostApprovalDecision,
    HostResultValidationError,
    MCPHostCompatibilityLayer,
    validate_host_result,
)

from tests.contract.test_mcp_host_provider_error_lifecycle import _runtime


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
    "payload",
    [
        MCPHostCompatibilityLayer.mock_only().call_tool(
            {
                "tool_name": "get_power_state",
                "target": "mock-host",
                "session_id": "schema-s1",
                "requester_id": "schema-host",
            }
        ),
        MCPHostCompatibilityLayer.mock_only().call_tool(
            {
                "tool_name": "reveal_secret",
                "target": "mock-host",
                "session_id": "schema-s1",
                "requester_id": "schema-host",
            }
        ),
        MCPHostCompatibilityLayer.mock_only().call_tool(
            {
                "tool_name": "force_restart",
                "target": "mock-host",
                "session_id": "schema-s1",
                "requester_id": "schema-host",
            }
        ),
        MCPHostCompatibilityLayer(runtime=_runtime()).call_tool(
            {
                "tool_name": "get_power_state",
                "target": "error-target",
                "provider": "error-provider",
                "session_id": "schema-s1",
                "requester_id": "schema-host",
                "params": {"error_name": "provider_timeout"},
            }
        ),
        MCPHostCompatibilityLayer.mock_only().call_tool(
            {
                "tool_name": "get_power_state",
                "target": "missing-target",
                "session_id": "schema-s1",
                "requester_id": "schema-host",
            }
        ),
    ],
)
def test_generated_host_results_pass_schema_validation(payload) -> None:
    validate_host_result(payload)


def test_approval_submission_result_passes_schema_validation() -> None:
    host = MCPHostCompatibilityLayer.mock_only()
    required = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "schema-s1",
            "requester_id": "schema-host",
        }
    )
    granted = host.submit_approval_response(_approval_response(required))

    validate_host_result(granted)


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        ({"tool_name": "x"}, "status"),
        ({"status": "surprise", "reason": "x"}, "status"),
        ({"status": "ok", "tool_name": "x"}, "reason"),
        (
            {
                "status": "approval_required",
                "tool_name": "force_restart",
                "target": "mock-host",
                "provider": "mock",
                "reason": "approval needed",
            },
            "approval_request",
        ),
        (
            {
                "status": "provider_error",
                "tool_name": "get_power_state",
                "target": "mock-host",
                "provider": "mock",
                "reason": "provider failed",
                "data": {"provider_result": {"status": "error"}},
            },
            "error_code",
        ),
        (
            {
                "status": "approval_granted",
                "reason": "approval granted",
            },
            "request_id",
        ),
    ],
)
def test_malformed_host_results_fail_closed(payload, match) -> None:
    with pytest.raises(HostResultValidationError, match=match):
        validate_host_result(payload)


def test_host_result_schema_rejects_raw_bytes_and_exception_objects() -> None:
    with pytest.raises(HostResultValidationError, match="JSON-safe"):
        validate_host_result(
            {
                "status": "ok",
                "tool_name": "observe_screen",
                "target": "mock-host",
                "provider": "mock",
                "reason": "bad bytes",
                "data": {"raw": b"raw screenshot bytes"},
            }
        )

    with pytest.raises(HostResultValidationError, match="JSON-safe"):
        validate_host_result(
            {
                "status": "validation_error",
                "reason": "bad exception",
                "details": {"exception": RuntimeError("must not leak")},
            }
        )


def test_host_result_schema_rejects_unredacted_sensitive_keys() -> None:
    with pytest.raises(HostResultValidationError, match="credential_ref"):
        validate_host_result(
            {
                "status": "ok",
                "tool_name": "get_status",
                "target": "mock-host",
                "provider": "mock",
                "reason": "bad credential",
                "credential_ref": "vault://prod/not-for-tests",
            }
        )

    validate_host_result(
        {
            "status": "ok",
            "tool_name": "get_status",
            "target": "mock-host",
            "provider": "mock",
            "reason": "redacted credential",
            "credential_ref": "[REDACTED]",
        }
    )
