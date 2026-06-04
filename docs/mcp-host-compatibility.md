# MCP Host Compatibility

AgenticKVM includes a dependency-free, mock-only MCP host compatibility layer.
It models how a future MCP host should list tools, fetch schemas, call tools,
handle `approval_required`, and serialize errors without importing a real MCP
SDK or opening a server.

This layer is not an authority boundary and is not a live MCP server.

## Safety Path

Every host-style call must route through the existing AgenticKVM path:

```text
host compatibility request
-> MCPSDKAdapter
-> MCPRouter
-> provider registry
-> target registry
-> capability registry
-> ControlPlane
-> approval if required
-> provider adapter only if allowed
-> audit event
-> structured result
```

The host compatibility layer must not call providers directly.

## Supported Local Operations

- list registered tools
- get a JSON-safe tool schema
- call a tool through the mock-only SDK adapter
- serialize a structured result
- serialize a structured error

The layer does not:

- open a listener
- start a daemon
- import a live MCP SDK
- enable real providers by default
- resolve credentials
- read environment secrets
- auto-approve gated actions

## Mock-Only Usage

```python
from agentickvm.mcp_sdk import MCPHostCompatibilityLayer

host = MCPHostCompatibilityLayer.mock_only()
tools = host.list_tools()
schema = host.get_tool_schema("get_power_state")
result = host.call_tool(
    {
        "tool_name": "get_power_state",
        "target": "mock-host",
        "session_id": "local-host-session",
        "requester_id": "local-host",
    }
)
```

This runs entirely in process with the built-in mock configuration. It does not
start a listener and does not contact any provider over the network.

## Results

Host results preserve the MCP adapter result statuses:

- `ok`
- `denied`
- `approval_required`
- `validation_error`
- `provider_error`
- `policy_error`

`approval_required` is a first-class outcome. It must be returned to the caller
as structured data and must not be treated as implicit approval.

## Schemas

Tool schemas are JSON-safe and include:

- tool name
- mapped capability
- description
- dangerous-action flag when known
- required inputs
- possible result statuses

Schemas must not include real targets, real hostnames, real IP addresses,
tokens, passwords, cookies, credential examples, or provider internals that
would allow bypassing policy.

## Future MCP SDK Integration

A future real MCP SDK server adapter must conform to this compatibility layer
before live provider work is exposed through MCP. That future adapter remains a
separate decision and must still be mock-only by default.
