# Implementation Plan: MCP SDK Adapter

## Phase 1: Dependency Decision

- Evaluate MCP SDK dependency.
- Confirm supported Python version and packaging impact.
- Decision for current lane: dependency-free internal scaffold first.

## Phase 2: Mock-Only Adapter

- Translate SDK tool calls into `MCPToolRequest`.
- Route through `MCPRouter`.
- Return `MCPToolResult.to_dict()`.
- Use built-in mock config by default.
- Allow explicit fixture configs for offline tests only.

## Phase 3: Contract Tests

- Unknown tool fails closed.
- Mock observe succeeds.
- Dangerous action returns approval-required or denied.
- Provider calls occur only through `ControlPlane`.
- Adapter does not import or call providers directly.
- Adapter does not start a live server or read credentials.

## Deferred

- Live provider adapter tests.
- Credential resolution.
- Live approval transport.
