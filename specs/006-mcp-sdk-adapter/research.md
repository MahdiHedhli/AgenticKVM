# Research: MCP SDK Adapter

## Adapter Boundary

The SDK adapter should translate external SDK tool invocations into
`MCPToolRequest` and pass them to `MCPRouter`. It should not import provider
adapters, instantiate providers directly, or evaluate policy.

## Dependency Decision

The SDK dependency is not selected yet. The current implementation uses a
dependency-free internal scaffold. Before adding a real SDK package, verify:

- Python 3.13 support
- package stability
- license
- testability without live clients
- JSON serialization behavior
- local-only mock testing path

## Result Shape

The adapter should return `MCPToolResult.to_dict()` unchanged unless the SDK
requires a wrapper. This preserves:

- `ok`
- `denied`
- `approval_required`
- `validation_error`
- `provider_error`
- `policy_error`

## Manual Test Plan

First adapter tests should be local, mock-only, and run without credentials or
network. Live provider tests remain deferred.

## Current Implementation Notes

- `src/agentickvm/mcp_sdk/adapter.py` wraps `MCPRouter`.
- `src/agentickvm/mcp_sdk/models.py` defines JSON-like tool call input.
- The adapter uses mock-only config by default.
- Explicit fixture configs may be used for offline PiKVM/Redfish tests.
- No listener, SDK server, network call, credential resolution, or provider
  bypass exists.
