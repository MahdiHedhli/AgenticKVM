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

## Mock Host Compatibility Example

```python
from agentickvm.mcp_sdk import MCPHostCompatibilityLayer

host = MCPHostCompatibilityLayer.mock_only()
print(host.list_tools())
print(host.get_tool_schema("get_power_state"))

result = host.call_tool(
    {
        "tool_name": "get_power_state",
        "target": "mock-host",
        "session_id": "host-demo-session",
        "requester_id": "host-demo",
    }
)
print(result["status"])
```

Expected status: `ok`. This is a local compatibility boundary, not a live MCP
server.

## Mock Approval Resumption

```python
from agentickvm.mcp_sdk import MCPHostCompatibilityLayer

host = MCPHostCompatibilityLayer.mock_only()
required = host.call_tool(
    {
        "tool_name": "force_restart",
        "target": "mock-host",
        "session_id": "approval-demo-session",
        "requester_id": "host-demo",
    }
)

approval = required["approval_request"]
response = {
    "request_id": approval["id"],
    "decision": "granted",
    "operator_id": "operator-demo",
    "scope": "one_time",
    "session_id": approval["session_id"],
    "target": approval["target"],
    "provider": approval["provider"],
    "capability": approval["capability"],
    "params_fingerprint": approval["params_fingerprint"],
}

print(host.submit_approval_response(response)["status"])
print(host.resume_approved_tool(approval["id"])["status"])
```

Expected statuses: `approval_granted`, then `ok`. The approval response is
explicit; the host does not auto-approve.

## Mock Audit Persistence

```python
from agentickvm.mcp_sdk import MCPHostCompatibilityLayer

host = MCPHostCompatibilityLayer.mock_only(
    audit_path="/tmp/agentickvm-host-demo-audit.jsonl"
)
host.call_tool(
    {
        "tool_name": "get_power_state",
        "target": "mock-host",
        "session_id": "audit-demo-session",
        "requester_id": "host-demo",
    }
)
```

Tests use temporary audit paths and verify the JSONL hash chain.

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
- The host compatibility layer does not open a listener and does not
  auto-approve gated actions.
- Approval resumption is mock-only and still routes through `ControlPlane`.
- Audit persistence tests use explicit local paths.
