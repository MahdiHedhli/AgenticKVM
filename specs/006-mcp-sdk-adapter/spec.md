# Specification: MCP SDK Adapter

## Status

Research and design draft. No live MCP SDK server is implemented in this spec.

## Goal

Define the future MCP SDK adapter as a thin translation layer over the existing
MCP router.

## Scope

In scope:

- SDK adapter boundary
- mock-only first adapter plan
- JSON-safe result contract
- approval-required result behavior
- no provider bypass rule

Out of scope:

- SDK dependency selection
- live MCP client tests
- live provider execution
- credential loading
- approval transport UI

## Requirements

- MCP SDK adapter is not an authority boundary.
- Adapter routes to the existing `MCPRouter`.
- Adapter cannot call providers directly.
- Mock-only first.
- No real providers by default.
- No credentials.
- Unknown tools fail closed.
- Unknown targets fail closed.
- Structured `approval_required` results remain first-class.
- Results must be JSON-safe and secret-redacted.
