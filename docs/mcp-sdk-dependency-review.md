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

- candidate package name and exact version
- maintainer, source repository, and release provenance
- license compatibility
- release cadence and security advisory history
- transitive dependency list
- supply-chain controls for installation and release
- Python 3.13 support
- package stability and release cadence
- dependency tree size and security posture
- JSON schema/tool-call behavior
- error serialization behavior
- supported transport modes
- stdio support
- socket, HTTP, or streaming server exposure model
- authentication and authorization model
- local-only mode
- testability without live hosts
- ability to run mock-only by default
- ability to preserve `approval_required` without auto-approval
- ability to route through `MCPHostCompatibilityLayer` or an equivalent
  adapter without provider bypass
- packaging risk for optional dependencies
- integration risk with current Python packaging
- operational risk if a listener is exposed
- ability to preserve host correlation ids
- ability to expose structured result ids if needed for audit correlation
- ability to avoid swallowing audit errors
- ability to surface audit-related failures distinctly enough for policy
  handling
- ability to avoid logging raw tool arguments, secrets, credential refs,
  screenshots, or raw provider payloads

## Candidate Package

- name:
- version:
- source:
- maintainer:
- license:
- release cadence:
- Python versions:
- transitive dependency count:
- known security advisories:

## Transport And Exposure Model

- stdio support:
- socket support:
- HTTP support:
- streaming support:
- default bind address:
- local-only mode:
- authentication model:
- authorization model:
- logging behavior:
- error serialization behavior:
- schema serialization behavior:

## Supply-Chain And Packaging Risk

- package manager strategy:
- optional dependency strategy:
- lockfile impact:
- transitive dependency review:
- vendored code:
- native extensions:
- install-time scripts:
- update cadence:
- license risk:

## Security Review Questions

- Can the server run in mock-only mode without credentials?
- Can CI run all SDK tests without live network access?
- Can tool calls be forced through `MCPHostCompatibilityLayer` or an equivalent
  safety adapter?
- Can `approval_required` be returned without triggering implicit approval?
- Can provider errors be serialized without leaking raw exception details?
- Can screenshot and artifact metadata be returned without raw bytes?
- Can the SDK be configured so real providers are disabled by default?
- Can credential resolution remain outside the SDK server by default?
- Can the server run without reading environment secrets?
- Can the server avoid opening public listeners by default?
- Can logs and traces avoid secrets, credential refs, screenshots, and raw
  provider payloads?
- Can the SDK preserve approval-required results without mutating state?
- Can the SDK preserve host correlation ids across approval and audit flows?
- Can the SDK avoid swallowing audit errors?
- Can the SDK support local-only/mock-only test mode for audit checkpoint and
  export tests?
- Can the SDK preserve JSON-safe results and reject unsafe result shapes?
- Can the SDK avoid background network listeners unless explicitly configured?

## Required Tests Before Adoption

- tool listing stays JSON-safe
- tool schema output contains no secrets or live endpoints
- tool calls route through `MCPSDKAdapter`, `MCPRouter`, registries, and
  `ControlPlane`
- approval-required results are preserved
- approval response submission remains explicit
- one-time and session approval resumption still match exact scope
- approval resumption still surfaces provider errors
- audit JSONL persistence remains hash-chain verifiable
- audit tampering, middle-event deletion, and event reordering fail verification
- checkpoint-backed tail-truncation detection passes
- audit export/import verification passes
- retention policy validation rejects silent deletion
- audit failure blocks high-risk execution and approval consumption
- artifact metadata is emitted without raw screenshot bytes
- golden host result fixtures still match generated results
- host result schema validation passes for valid results and rejects unsafe
  shapes
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
