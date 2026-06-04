# MCP SDK Adapter

AgenticKVM now includes a dependency-free mock-only MCP SDK adapter scaffold.
It models the future SDK boundary without importing a real SDK, opening a live
server, resolving credentials, or reaching live providers.

No live MCP SDK server is implemented yet.

## Future Boundary

The SDK adapter is a translator:

```text
SDK tool call -> MCPToolRequest -> MCPRouter -> registries -> ControlPlane -> result
```

It must not:

- call providers directly
- instantiate live providers
- read credentials
- change policy
- auto-approve gated actions
- bypass target or provider registries

## Mock-Only First

The adapter uses the built-in mock-only config by default. Explicit fixture
configs may be passed for offline PiKVM/Redfish fixture tests. Real provider
targets remain disabled unless future readiness gates pass.

The dependency decision for this lane is: no external MCP SDK dependency.
The internal scaffold is used until package, Python version, security, and live
host integration questions are settled.

## Result Contract

Return the existing MCP result dictionary:

- `ok`
- `denied`
- `approval_required`
- `validation_error`
- `provider_error`
- `policy_error`

Approval-required is not a failure and not an implicit approval.

## Current Import

```python
from agentickvm.mcp_sdk import MCPSDKAdapter

adapter = MCPSDKAdapter.mock_only()
result = adapter.call_tool(
    {
        "tool_name": "get_power_state",
        "target": "mock-host",
        "session_id": "local-sdk-session",
        "requester_id": "local-sdk",
    }
)
```

## Deferred Decisions

- real MCP SDK dependency
- live SDK server/listener
- live MCP host integration tests
- live provider SDK tests
- approval transport UI
- credential resolution
