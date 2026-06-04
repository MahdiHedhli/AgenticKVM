import json

import pytest

from agentickvm.mcp_sdk.host_models import (
    HOST_RESULT_STATUSES,
    HostError,
    HostResultStatus,
    HostToolCall,
    HostToolDescriptor,
    HostToolResult,
    HostToolSchema,
)


def test_host_tool_descriptor_serializes_to_json_safe_dict() -> None:
    descriptor = HostToolDescriptor(
        tool_name="observe_screen",
        capability="observe.screenshot",
        description="Observe screen.",
    )

    payload = descriptor.to_dict()

    assert payload["tool_name"] == "observe_screen"
    assert payload["capability"] == "observe.screenshot"
    json.dumps(payload)


def test_host_tool_schema_redacts_secret_like_fields() -> None:
    schema = HostToolSchema(
        tool_name="observe_screen",
        capability="observe.screenshot",
        description="Observe screen.",
        dangerous=False,
        input_schema={
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "token_example": "must-not-leak-host-secret",
            },
        },
    )

    payload = schema.to_dict()

    assert payload["status"] == "ok"
    assert payload["possible_statuses"] == list(HOST_RESULT_STATUSES)
    assert "must-not-leak-host-secret" not in repr(payload)
    assert payload["input"]["properties"]["token_example"] == "[REDACTED]"
    json.dumps(payload)


def test_host_tool_schema_from_adapter_schema() -> None:
    schema = HostToolSchema.from_adapter_schema(
        {
            "status": "ok",
            "tool_name": "force_restart",
            "capability": "power.force_restart",
            "description": "Force restart.",
            "dangerous": True,
            "input": {"type": "object", "required": ["target"]},
        }
    )

    payload = schema.to_dict()

    assert payload["dangerous"] is True
    assert "approval_required" in payload["possible_statuses"]


def test_host_tool_schema_from_unknown_adapter_schema_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown MCP tool"):
        HostToolSchema.from_adapter_schema(
            {
                "status": "validation_error",
                "tool_name": "unknown",
                "reason": "unknown MCP tool",
            }
        )


def test_host_tool_call_from_mapping_validates_shape() -> None:
    call = HostToolCall.from_mapping(
        {
            "tool_name": "get_power_state",
            "target": "mock-host",
            "params": {"detail": True},
            "ignored": "safe",
        }
    )

    assert call.tool_name == "get_power_state"
    assert call.target == "mock-host"
    assert call.session_id == "host-session"
    assert call.requester_id == "mcp-host"
    assert dict(call.params) == {"detail": True}


def test_host_tool_call_rejects_malformed_params() -> None:
    with pytest.raises(ValueError, match="params must be an object"):
        HostToolCall.from_mapping(
            {
                "tool_name": "get_power_state",
                "target": "mock-host",
                "params": ["not", "an", "object"],
            }
        )


def test_host_tool_result_preserves_approval_required_and_redacts_data() -> None:
    result = HostToolResult.from_adapter_result(
        {
            "status": "approval_required",
            "tool_name": "force_restart",
            "capability": "power.force_restart",
            "target": "mock-host",
            "provider": "mock-provider",
            "reason": "operator approval required",
            "data": {"params_preview": {"password": "must-not-leak-host-secret"}},
            "approval_request_id": "approval-1",
            "risks": ["power interruption"],
        }
    )

    payload = result.to_dict()

    assert payload["status"] == "approval_required"
    assert payload["approval_request_id"] == "approval-1"
    assert "must-not-leak-host-secret" not in repr(payload)
    assert payload["data"]["params_preview"]["password"] == "[REDACTED]"
    assert "data.params_preview.password" in payload["redactions"]
    json.dumps(payload)


def test_host_error_redacts_reason_and_details() -> None:
    error = HostError(
        status=HostResultStatus.PROVIDER_ERROR,
        reason="provider token must-not-leak-host-secret failed",
        tool_name="observe_screen",
        details={"session_cookie": "must-not-leak-host-secret"},
    )

    payload = error.to_dict()

    assert payload["status"] == "provider_error"
    assert payload["reason"] == "[REDACTED]"
    assert payload["details"]["session_cookie"] == "[REDACTED]"
    assert "must-not-leak-host-secret" not in repr(payload)
    json.dumps(payload)


def test_host_error_rejects_success_status() -> None:
    with pytest.raises(ValueError, match="host errors must use an error status"):
        HostError(status=HostResultStatus.OK, reason="not an error")
