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
- submit an explicit approval response
- resume a pending approved tool call
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

For audit persistence tests, pass an explicit local JSONL path:

```python
host = MCPHostCompatibilityLayer.mock_only(audit_path="/tmp/agentickvm-host-audit.jsonl")
```

Tests use temporary directories. Production audit-store requirements remain
deferred.

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

## Approval Lifecycle

When a host call returns `approval_required`, the host compatibility layer must
preserve approval metadata for an explicit operator or test-fixture response.

The approval response must match the pending action by:

- approval request id
- session id
- target id
- provider id
- capability id
- safe parameter fingerprint
- approval scope
- expiry time

One-time approvals are consumed by exactly one matching resumed execution.
Session approvals may be reused only for the exact same session, target,
provider, capability, and parameter fingerprint.

The host cannot auto-approve. A future live MCP server must surface
`approval_required` to the caller and wait for an explicit approval response.

Approval responses cannot authorize policy modification, audit disabling,
emergency stop disabling, raw secret reveal by default, target expansion, or
provider expansion.

The local methods are:

- `submit_approval_response(response)`
- `resume_approved_tool(approval_request_id)`

Submitting an approval response only creates a matching approval grant in the
runtime approval store. It does not execute the action. Resumption calls back
through the host layer, SDK adapter, MCP router, registries, and
`ControlPlane`.

## Audit Persistence

Host-compatible mock flows may use an explicit local JSONL audit path for
tests. Audit records are hash-chained, redacted, and written only to the
configured path. Tests use temporary directories only.

The approval lifecycle must audit:

- approval requested
- approval granted, denied, or expired
- approval consumed
- provider execution when execution occurs
- final result

Hash-chain verification is performed with `verify_audit_chain`. Tampered JSONL
records must fail verification.

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
