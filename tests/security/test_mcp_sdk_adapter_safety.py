import inspect

import agentickvm.mcp_sdk.adapter as adapter_module
from agentickvm.mcp_sdk import MCPSDKAdapter


def test_mcp_sdk_adapter_does_not_call_providers_directly() -> None:
    source = inspect.getsource(adapter_module)

    assert "execute_authorized" not in source
    assert "MockProvider" not in source
    assert "PiKVMObserveProvider" not in source
    assert "RedfishObserveProvider" not in source


def test_mcp_sdk_adapter_has_no_live_network_imports() -> None:
    source = inspect.getsource(adapter_module)

    for forbidden in (
        "import requests",
        "from requests",
        "import urllib",
        "from urllib",
        "import http.client",
        "from http.client",
        "import socket",
        "from socket",
    ):
        assert forbidden not in source


def test_mcp_sdk_adapter_does_not_read_environment_secrets(monkeypatch) -> None:
    monkeypatch.setenv("AGENTICKVM_PASSWORD", "must-not-leak-sdk-secret")
    monkeypatch.setenv("AGENTICKVM_TOKEN", "must-not-leak-sdk-secret")
    adapter = MCPSDKAdapter.mock_only()

    result = adapter.call_tool(
        {
            "tool_name": "get_status",
            "target": "mock-host",
            "session_id": "s1",
            "requester_id": "sdk-test",
        }
    )

    assert result["status"] == "ok"
    assert "must-not-leak-sdk-secret" not in repr(result)


def test_mcp_sdk_adapter_output_redacts_secret_shaped_inputs() -> None:
    adapter = MCPSDKAdapter.mock_only()

    result = adapter.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "s1",
            "requester_id": "sdk-test",
            "params": {
                "password": "must-not-leak-sdk-secret",
                "token": "must-not-leak-sdk-secret",
            },
        }
    )

    assert result["status"] == "approval_required"
    assert "must-not-leak-sdk-secret" not in repr(result)
    assert "params.password" in result["redactions"]
    assert "params.token" in result["redactions"]


def test_mcp_sdk_adapter_does_not_auto_approve() -> None:
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
    assert result["data"]["policy_decision"] == "ask_each_time"
