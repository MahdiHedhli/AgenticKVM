# MCP SDK Adapter Quickstart

This quickstart uses the dependency-free internal MCP SDK adapter scaffold. It
does not start a live MCP server, use credentials, contact real providers, or
touch hardware.

## Mock-Only Tool Call

```python
from agentickvm.mcp_sdk import MCPSDKAdapter

adapter = MCPSDKAdapter.mock_only()
print(adapter.list_tools())

result = adapter.call_tool(
    {
        "tool_name": "get_power_state",
        "target": "mock-host",
        "session_id": "demo-session",
        "requester_id": "demo-sdk",
    }
)
print(result)
```

Expected status: `ok`.

## Approval-Required Result

```python
result = adapter.call_tool(
    {
        "tool_name": "force_restart",
        "target": "mock-host",
        "session_id": "demo-session",
        "requester_id": "demo-sdk",
    }
)
print(result["status"])
```

Expected status: `approval_required`. The adapter does not auto-approve.

## PiKVM Fixture-Only Example

```python
from agentickvm.mcp_sdk import MCPSDKAdapter

adapter = MCPSDKAdapter.from_config("examples/config/pikvm-observe-fixture.yaml")
result = adapter.call_tool(
    {
        "tool_name": "observe_screen",
        "target": "pikvm-fixture-target",
        "provider": "pikvm-fixture",
        "session_id": "fixture-session",
        "requester_id": "fixture-sdk",
    }
)
print(result["status"])
```

Expected status: `ok`. This is synthetic fixture output, not live PiKVM output.

## Run Tests

```text
uv run --with pytest --python python3.13 python -m pytest
```

## Safety Notes

- The adapter is not an authority boundary.
- Calls route through `MCPRouter`, registries, policy, approval/audit, and
  `ControlPlane`.
- Unknown tools and unknown targets fail closed.
- Disabled providers and disabled targets fail closed.
- Credential references are not resolved.
- Live providers remain deferred.
- No real MCP SDK server is started.
