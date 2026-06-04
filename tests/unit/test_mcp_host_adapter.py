from agentickvm.mcp_sdk import MCPHostCompatibilityLayer, HostToolCall


def test_mcp_host_compatibility_imports() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    assert isinstance(host, MCPHostCompatibilityLayer)


def test_mcp_host_lists_registered_tools() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    result = host.list_tools()

    assert result["status"] == "ok"
    assert {"observe_screen", "get_power_state", "force_restart"} <= {
        tool["tool_name"] for tool in result["tools"]
    }
    assert all("capability" in tool for tool in result["tools"])


def test_mcp_host_returns_tool_schema() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    schema = host.get_tool_schema("observe_screen")

    assert schema["status"] == "ok"
    assert schema["tool_name"] == "observe_screen"
    assert schema["capability"] == "observe.screenshot"
    assert schema["input"]["required"] == ["target"]
    assert "approval_required" in schema["possible_statuses"]


def test_mcp_host_unknown_tool_schema_fails_closed() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    schema = host.get_tool_schema("unknown_tool")

    assert schema["status"] == "validation_error"
    assert schema["reason"] == "unknown MCP tool"


def test_mcp_host_observe_mock_target_succeeds() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    result = host.call_tool(
        HostToolCall(
            tool_name="observe_screen",
            target="mock-host",
            session_id="host-s1",
            requester_id="host-test",
        )
    )

    assert result["status"] == "ok"
    assert result["capability"] == "observe.screenshot"
    assert result["data"]["provider_result"]["performed_on_hardware"] is False


def test_mcp_host_preserves_approval_required() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    result = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "host-s1",
            "requester_id": "host-test",
        }
    )

    assert result["status"] == "approval_required"
    assert result["capability"] == "power.force_restart"
    assert "approval_request_id" in result


def test_mcp_host_unknown_tool_fails_closed() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    result = host.call_tool(
        {
            "tool_name": "unknown_tool",
            "target": "mock-host",
            "session_id": "host-s1",
            "requester_id": "host-test",
        }
    )

    assert result["status"] == "validation_error"
    assert result["reason"] == "unknown MCP tool"


def test_mcp_host_malformed_request_serializes_validation_error() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    result = host.call_tool({"tool_name": "observe_screen"})

    assert result["status"] == "validation_error"
    assert result["reason"] == "host target is required"
    assert result["tool_name"] == "observe_screen"
