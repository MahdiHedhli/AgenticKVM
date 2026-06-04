# MCP SDK Adapter

AgenticKVM now includes a dependency-free mock-only MCP SDK adapter scaffold.
It models the future SDK boundary without importing a real SDK, opening a live
server, resolving credentials, or reaching live providers.

No live MCP SDK server is implemented yet.

AgenticKVM also includes a dependency-free mock-only host compatibility layer
over this adapter. The host layer models future MCP host behavior for local
tests only; it is not a live MCP server and does not open a listener.

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
- open a network listener

## Mock-Only First

The adapter uses the built-in mock-only config by default. Explicit fixture
configs may be passed for offline PiKVM/Redfish fixture tests. Real provider
targets remain disabled unless future readiness gates pass.

The dependency decision for this lane is: no external MCP SDK dependency.
The internal scaffold is used until package, Python version, security, and live
host integration questions are settled.

Dependency review requirements are tracked in
`docs/mcp-sdk-dependency-review.md`.

## Result Contract

Return the existing MCP result dictionary:

- `ok`
- `denied`
- `approval_required`
- `validation_error`
- `provider_error`
- `policy_error`

Approval-required is not a failure and not an implicit approval.

## Host Compatibility Layer

The local host compatibility layer is imported as:

```python
from agentickvm.mcp_sdk import MCPHostCompatibilityLayer
```

It exposes local methods for:

- `list_tools()`
- `get_tool_schema(tool_name)`
- `call_tool(request)`
- `submit_approval_response(response)`
- `resume_approved_tool(approval_request_id)`
- `serialize_result(result)`
- `serialize_error(error)`

All calls route through `MCPSDKAdapter`. Tool schemas include the tool name,
mapped capability, description, dangerous-action flag, required inputs, and
possible result statuses. Schemas are JSON-safe and must not contain secrets,
live hostnames, live IP addresses, or credential examples.

The host compatibility layer preserves `approval_required` and never
auto-approves gated actions.

Approval submission and resumption are mock-only fixture flows. An approval
response creates an exact grant in the runtime approval store. Resumed
execution still routes through `MCPSDKAdapter`, `MCPRouter`, registries, and
`ControlPlane`.

The host layer can be created with an explicit local JSONL audit path for tests.
Audit records are redacted and hash-chained; tampered records must fail
verification.

The host compatibility suite now includes provider-error lifecycle fixtures,
approval-resumption/provider-error fixtures, audit lifecycle integrity checks,
artifact metadata-only checks, golden result fixtures, and lightweight host
result schema validation. A future real MCP SDK/server adapter must preserve
these behaviors before it is allowed to expose live provider work.

The result validator is available as:

```python
from agentickvm.mcp_sdk import validate_host_result
```

It rejects unknown statuses, missing required fields, raw bytes, exception
objects, unsafe provider-error shapes, malformed approval shapes, and
unredacted secret-shaped keys.

Production audit-store readiness is also a dependency for future live server
work. A real MCP SDK/server adapter must preserve checkpoint-backed
tail-truncation detection, audit export/import verification, retention policy
rules, and fail-closed audit failure behavior.

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
- production audit-store checkpointing and retention
