# MCP SDK Dependency Review Template

## Status

Template only. No MCP SDK dependency has been selected or added.

## Purpose

Before AgenticKVM adopts a real MCP SDK or implements a live MCP server, the
dependency and host integration model must be reviewed against the mock-only
host compatibility contract.

## Current Boundary

The current implementation is dependency-free:

- `MCPSDKAdapter` translates JSON-like calls into `MCPToolRequest`
- `MCPHostCompatibilityLayer` models future host behavior locally
- no listener is opened
- no live providers are enabled
- no credentials are resolved
- approval and audit behavior are tested with mocks and fixtures

## Review Checklist

A future MCP SDK dependency must be reviewed for:

- Python 3.13 support
- package stability and release cadence
- license compatibility
- dependency tree size and security posture
- JSON schema/tool-call behavior
- error serialization behavior
- stdio/server transport options
- testability without live hosts
- ability to run mock-only by default
- ability to preserve `approval_required` without auto-approval
- ability to route through `MCPHostCompatibilityLayer` or an equivalent
  adapter without provider bypass

## Required Tests Before Adoption

- tool listing stays JSON-safe
- tool schema output contains no secrets or live endpoints
- tool calls route through `MCPSDKAdapter`, `MCPRouter`, registries, and
  `ControlPlane`
- approval-required results are preserved
- approval response submission remains explicit
- one-time and session approval resumption still match exact scope
- audit JSONL persistence remains hash-chain verifiable
- unknown tools and targets fail closed
- disabled providers fail closed
- no live provider path is exposed by default
- no credentials are required in CI

## Open Review Items

- exact SDK package name and version
- package manager and optional dependency strategy
- whether the first live adapter is stdio-only
- how host integration tests run without live providers
- whether approval UI/transport is separate from MCP server transport
- production audit-store requirements

## Decision Rule

Do not add a live MCP SDK/server dependency until the mock-only compatibility
contract, approval lifecycle, audit persistence, and provider bypass tests are
preserved by the real adapter.
