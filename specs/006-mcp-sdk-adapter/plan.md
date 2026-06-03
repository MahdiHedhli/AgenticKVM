# Implementation Plan: MCP SDK Adapter

## Phase 1: Dependency Decision

- Evaluate MCP SDK dependency.
- Confirm supported Python version and packaging impact.
- Keep the decision docs-only until dependency risk is understood.

## Phase 2: Mock-Only Adapter

- Translate SDK tool calls into `MCPToolRequest`.
- Route through `MCPRouter`.
- Return `MCPToolResult.to_dict()`.
- Use built-in mock config by default.

## Phase 3: Contract Tests

- Unknown tool fails closed.
- Mock observe succeeds.
- Dangerous action returns approval-required or denied.
- Provider calls occur only through `ControlPlane`.

## Deferred

- Live provider adapter tests.
- Credential resolution.
- Live approval transport.
