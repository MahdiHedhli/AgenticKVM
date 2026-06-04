from agentickvm.mcp_sdk import MCPSDKAdapter, MCPSDKToolCall


def test_mcp_sdk_adapter_imports() -> None:
    adapter = MCPSDKAdapter.mock_only()

    assert isinstance(adapter, MCPSDKAdapter)


def test_mcp_sdk_adapter_lists_registered_tools() -> None:
    adapter = MCPSDKAdapter.mock_only()

    tools = adapter.list_tools()

    assert {"observe_screen", "get_power_state", "force_restart"} <= {
        tool["tool_name"] for tool in tools
    }
    assert all("capability" in tool for tool in tools)


def test_mcp_sdk_adapter_returns_tool_schema_metadata() -> None:
    adapter = MCPSDKAdapter.mock_only()

    schema = adapter.tool_schema("observe_screen")
    unknown = adapter.tool_schema("unknown_tool")

    assert schema["status"] == "ok"
    assert schema["capability"] == "observe.screenshot"
    assert schema["input"]["required"] == ["target"]
    assert unknown["status"] == "validation_error"


def test_mcp_sdk_adapter_observe_mock_target_succeeds() -> None:
    adapter = MCPSDKAdapter.mock_only()

    result = adapter.call_tool(
        MCPSDKToolCall(
            tool_name="observe_screen",
            target="mock-host",
            session_id="s1",
            requester_id="sdk-test",
        )
    )

    assert result["status"] == "ok"
    assert result["capability"] == "observe.screenshot"
    assert result["data"]["provider_result"]["performed_on_hardware"] is False


def test_mcp_sdk_adapter_unknown_tool_fails_closed() -> None:
    adapter = MCPSDKAdapter.mock_only()

    result = adapter.call_tool(
        {
            "tool_name": "unknown_tool",
            "target": "mock-host",
            "session_id": "s1",
            "requester_id": "sdk-test",
        }
    )

    assert result["status"] == "validation_error"
    assert result["reason"] == "unknown MCP tool"


def test_mcp_sdk_adapter_preserves_approval_required_result() -> None:
    adapter = MCPSDKAdapter.mock_only()

    result = adapter.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "s1",
            "requester_id": "sdk-test",
        }
    )

    assert result["status"] == "approval_required"
    assert result["capability"] == "power.force_restart"
    assert "approval_request_id" in result
