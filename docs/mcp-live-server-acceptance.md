# MCP Live Server Acceptance

## Status

Gate only. No live MCP server is implemented.

## Purpose

This document defines what a future live MCP SDK/server adapter must satisfy
before implementation, merge, and first live use. It complements
`docs/adr/0003-live-mcp-server-boundary.md` and
`specs/006-mcp-sdk-adapter/contracts/live-server-acceptance-gate.md`.

## Acceptance Summary

A live MCP server is an interface adapter. It must not become authority. The
server must preserve this route:

```text
MCP host/client
-> live MCP server adapter
-> MCP host compatibility contract
-> MCPSDKAdapter
-> MCPRouter
-> registries
-> ControlPlane
-> approval if required
-> provider adapter only if allowed
-> audit event
-> structured result
```

## Before Implementation

- Complete the dependency review framework.
- Complete the candidate matrix.
- Accept or update ADR 0003.
- Review production audit-store requirements.
- Complete packaging and supply-chain review.
- Write a mock-only adapter plan.
- Write a rollback plan.
- Keep real providers disabled by default.
- Keep credential resolution out of repo tests.
- Avoid network listeners by default.

## Before Merge

- Pass the full pytest suite.
- Pass host conformance fixtures through the SDK-backed adapter.
- Preserve JSON-safe tool listing and schema output.
- Preserve `approval_required` without auto-approval.
- Preserve explicit approval response submission.
- Preserve one-time and session approval resumption.
- Preserve audit lifecycle behavior.
- Preserve audit failure fail-closed behavior.
- Preserve audit checkpoint/export behavior.
- Preserve provider error taxonomy.
- Preserve artifact metadata-only behavior.
- Preserve redaction for secrets, credential references, screenshots, provider
  payloads, and raw tool arguments.
- Prove the server cannot call providers directly.
- Prove the server cannot bypass `MCPRouter`, registries, or `ControlPlane`.
- Prove CI is mock-only and cannot reach live providers.
- Document dependency versioning and optional extras.

## Before First Live Use

- Record operator approval.
- Configure local-only transport unless a stricter reviewed decision exists.
- Configure explicit audit path or production audit store.
- Acknowledge audit checkpoint/export behavior.
- Select credential strategy without committing credentials.
- Keep real providers disabled outside the approved smoke scope.
- Run mock-provider smoke first.
- Verify rollback path.

## Audit-Store Gate

The live server must preserve:

- audit write behavior
- audit failure behavior
- approval-requested, approval-granted, approval-denied, approval-expired, and
  approval-consumed audit events
- provider execution and provider error audit events
- artifact metadata audit events
- checkpoint-backed tail-truncation detection
- export/import verification
- retention policy constraints
- redaction before persistence

No raw screenshots, no raw secrets, no raw credential values, and no raw
provider payloads may be written to audit logs by default.

The live server adapter must not report success when required audit writes
fail. High-risk actions and approval consumption must fail closed if audit
emission, checkpoint-compatible persistence, or audit-error reporting is not
available. A future production warning-only mode for selected read-only actions
must be explicit policy, not SDK behavior.

## Required Mock Conformance Before Live Provider Exposure

Before any real provider is reachable through a live MCP server, the
SDK-backed adapter must pass mock-only tests for:

- ok result audit lifecycle
- denied result audit lifecycle
- approval-required lifecycle
- approval grant, denial, expiry, and consumption
- provider error audit lifecycle
- artifact metadata audit lifecycle
- checkpoint-backed tail-truncation detection
- audit export/import verification
- audit failure fail-closed behavior
- no audit writes outside explicit test paths

## Stop Conditions

Stop live server work if:

- dependency facts are unresolved in safety-critical areas
- dependency installation requires accepting unknown supply-chain risk
- the server requires live network for basic tests
- the server opens a listener by default
- the server bypasses host compatibility, `MCPRouter`, registries, or
  `ControlPlane`
- the server auto-approves or hides approval-required outcomes
- audit failures are swallowed
- secrets or raw tool arguments are logged
- CI can reach live providers
