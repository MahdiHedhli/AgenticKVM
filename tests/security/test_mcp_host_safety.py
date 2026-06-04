import inspect
import json
import re

import agentickvm.mcp_sdk.host as host_module
import agentickvm.mcp_sdk.host_models as host_models_module
from agentickvm.mcp_sdk import MCPHostCompatibilityLayer


def test_mcp_host_does_not_call_providers_directly() -> None:
    source = inspect.getsource(host_module)

    assert "execute_authorized" not in source
    assert "MockProvider" not in source
    assert "PiKVMObserveProvider" not in source
    assert "RedfishObserveProvider" not in source


def test_mcp_host_has_no_live_network_imports() -> None:
    source = inspect.getsource(host_module) + inspect.getsource(host_models_module)

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


def test_mcp_host_does_not_read_environment_secrets(monkeypatch) -> None:
    monkeypatch.setenv("AGENTICKVM_PASSWORD", "must-not-leak-host-secret")
    monkeypatch.setenv("AGENTICKVM_TOKEN", "must-not-leak-host-secret")
    host = MCPHostCompatibilityLayer.mock_only()

    result = host.call_tool(
        {
            "tool_name": "get_status",
            "target": "mock-host",
            "session_id": "host-s1",
            "requester_id": "host-test",
        }
    )

    assert result["status"] == "ok"
    assert "must-not-leak-host-secret" not in repr(result)


def test_mcp_host_output_redacts_secret_shaped_inputs() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    result = host.call_tool(
        {
            "tool_name": "force_restart",
            "target": "mock-host",
            "session_id": "host-s1",
            "requester_id": "host-test",
            "params": {
                "password": "must-not-leak-host-secret",
                "token": "must-not-leak-host-secret",
            },
        }
    )

    assert result["status"] == "approval_required"
    assert "must-not-leak-host-secret" not in repr(result)
    assert "params.password" in result["redactions"]
    assert "params.token" in result["redactions"]


def test_mcp_host_does_not_auto_approve() -> None:
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
    assert result["data"]["policy_decision"] == "ask_each_time"


def test_mcp_host_tool_schemas_are_json_safe_and_do_not_contain_live_values() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    for tool in host.list_tools()["tools"]:
        schema = host.get_tool_schema(tool["tool_name"])
        serialized = json.dumps(schema, sort_keys=True)

        assert schema["status"] == "ok"
        assert "password" not in serialized.lower()
        assert "token" not in serialized.lower()
        assert "api_key" not in serialized.lower()
        assert "session_cookie" not in serialized.lower()
        assert "example.com" not in serialized.lower()
        assert ".invalid" not in serialized.lower()
        assert re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", serialized) is None


def test_mcp_host_unknowns_fail_closed() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    unknown_tool = host.call_tool(
        {
            "tool_name": "missing_tool",
            "target": "mock-host",
            "session_id": "host-s1",
            "requester_id": "host-test",
        }
    )
    unknown_target = host.call_tool(
        {
            "tool_name": "get_power_state",
            "target": "missing-target",
            "session_id": "host-s1",
            "requester_id": "host-test",
        }
    )

    assert unknown_tool["status"] == "validation_error"
    assert unknown_target["status"] == "validation_error"


def test_mcp_host_has_no_remote_desktop_provider_behavior() -> None:
    source = inspect.getsource(host_module) + inspect.getsource(host_models_module)

    for forbidden in ("RustDesk", "VNC", "RDP", "MeshCentral", "clipboard", "file transfer"):
        assert forbidden not in source
