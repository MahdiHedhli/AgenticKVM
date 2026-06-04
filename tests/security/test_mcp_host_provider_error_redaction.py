from tests.contract.test_mcp_host_provider_error_lifecycle import _runtime

from agentickvm.mcp_sdk import MCPHostCompatibilityLayer


def test_mcp_host_provider_error_detail_is_redacted() -> None:
    host = MCPHostCompatibilityLayer(runtime=_runtime())

    result = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "error-target",
            "provider": "error-provider",
            "session_id": "provider-error-session",
            "requester_id": "provider-error-host",
            "params": {
                "error_name": "provider_protocol",
                "token": "must-not-leak-provider-error-secret",
            },
        }
    )

    assert result["status"] == "provider_error"
    assert "must-not-leak-provider-error-secret" not in repr(result)
    assert result["data"]["provider_result"]["warnings"] == ["[REDACTED]"]


def test_mcp_host_auth_provider_errors_do_not_expose_credential_detail() -> None:
    host = MCPHostCompatibilityLayer(runtime=_runtime())

    result = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "error-target",
            "provider": "error-provider",
            "session_id": "provider-error-session",
            "requester_id": "provider-error-host",
            "params": {"error_name": "provider_authentication_required"},
        }
    )
    provider_result = result["data"]["provider_result"]

    assert result["status"] == "provider_error"
    assert provider_result["error_code"] == "provider_authentication_required"
    assert provider_result["warnings"] == []
    assert "credential" not in provider_result["error_message"].lower()
    assert "must-not-leak-provider-error-secret" not in repr(result)


def test_mcp_host_unsafe_and_mutation_errors_are_not_approval_required() -> None:
    host = MCPHostCompatibilityLayer(runtime=_runtime())

    unsafe = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "error-target",
            "provider": "error-provider",
            "session_id": "provider-error-session",
            "requester_id": "provider-error-host",
            "params": {"error_name": "provider_unsafe_operation"},
        }
    )
    mutation = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "error-target",
            "provider": "error-provider",
            "session_id": "provider-error-session",
            "requester_id": "provider-error-host",
            "params": {"error_name": "provider_mutation_blocked"},
        }
    )

    assert unsafe["status"] == "provider_error"
    assert mutation["status"] == "provider_error"
    assert unsafe["data"]["provider_result"]["retryable"] is False
    assert mutation["data"]["provider_result"]["retryable"] is False
