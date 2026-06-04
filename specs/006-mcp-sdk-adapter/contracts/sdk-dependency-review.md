# MCP SDK Dependency Review Contract

## Status

Proposed. This contract defines the evidence and safety gates required before
AgenticKVM may trial, select, or add a real MCP SDK/server dependency.

## Purpose

AgenticKVM currently uses a dependency-free, mock-only MCP SDK adapter and host
compatibility layer. A future live MCP SDK/server dependency may be evaluated
only if it preserves the existing authority path:

```text
host request
-> MCP SDK adapter
-> MCP router
-> provider registry
-> target registry
-> capability registry
-> ControlPlane
-> approval if required
-> provider adapter only if allowed
-> audit event
-> structured result
```

The SDK/server is not an authority boundary.

## Required Evidence

Every candidate review must cite primary sources where available:

- project repository
- package registry page
- license file
- official documentation
- official transport documentation
- official security documentation
- release notes or release tags
- dependency metadata or lockfile analysis

If a fact cannot be verified, it must be marked `TODO` or `unknown`. Unknown
facts in authority routing, audit, approval, provider bypass, secret handling,
or CI isolation prevent selection.

## Project Fit Requirements

A candidate must be evaluated for:

- Python version compatibility with `agentickvm`
- packaging compatibility with `pyproject.toml` and `uv.lock`
- license compatibility
- maintenance signal and release cadence
- API stability
- documentation quality
- supported transport modes
- stdio support
- local-only or mock-only operation
- ability to run tests without live network access
- optional dependency behavior
- transitive dependency footprint
- installation and release provenance

## Security Fit Requirements

A candidate must be evaluated for:

- no automatic network exposure by default
- no hidden listener by default
- no telemetry by default, or telemetry clearly documented and disableable
- no credential logging
- no raw tool argument logging
- no raw screenshot or artifact logging
- no auto-approval behavior
- no background task execution without explicit configuration
- no provider bypass
- structured error support
- JSON-safe response support
- ability to preserve `approval_required`
- ability to preserve `audit_error` or equivalent audit failure signaling
- ability to preserve correlation IDs
- ability to constrain operation to local stdio if selected
- resistance to token passthrough, SSRF, session hijacking, and local server
  exposure risks documented by MCP security guidance

## AgenticKVM Conformance Requirements

Before a dependency can be adopted, an SDK-backed adapter must pass the current
mock-only conformance suite and prove:

- host compatibility behavior is preserved
- tool listing and tool schemas remain JSON-safe
- unknown tools fail closed
- unknown targets fail closed
- disabled providers fail closed
- tool calls route through `MCPRouter`
- tool calls route through registries and `ControlPlane`
- no provider is called directly
- no real provider is instantiated by default
- no credentials or credential references are resolved by default
- `approval_required` is preserved without auto-approval
- approval resumption remains explicit and scope-bound
- audit lifecycle behavior is preserved
- audit failure behavior is preserved
- audit checkpoint/export behavior is preserved
- provider error taxonomy is preserved
- artifact metadata policy is preserved
- host result schema validation remains compatible

## Rejection Conditions

Reject a candidate if it:

- requires provider calls outside `ControlPlane`
- requires real providers in CI
- requires live network access for basic tests
- requires raw credentials in config or test fixtures
- opens public listeners by default
- logs raw tool arguments, secrets, screenshots, or provider payloads by
  default without a disable-and-test path
- cannot preserve approval-required results
- cannot surface audit failures distinctly enough to fail closed
- cannot run mock-only
- conflicts with the AgenticKVM constitution

## Required Artifacts

Before dependency selection, the repo must contain:

- `docs/mcp-sdk-dependency-review.md`
- `docs/mcp-sdk-candidate-matrix.md`
- `docs/adr/0003-live-mcp-server-boundary.md`
- `docs/mcp-live-server-acceptance.md`
- `specs/006-mcp-sdk-adapter/contracts/sdk-dependency-review.md`
- `specs/006-mcp-sdk-adapter/contracts/live-server-acceptance-gate.md`
- documentation gate tests proving these artifacts exist and include approval,
  audit, mock-only, no-provider-bypass, and no-secret requirements

## Non-Goals For This Lane

- selecting a dependency
- adding a dependency
- implementing a live MCP server
- opening a network listener
- enabling real providers
- resolving credentials
- performing live provider smoke tests
