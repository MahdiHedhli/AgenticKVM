# ADR 0003: Live MCP Server Boundary

## Status

Proposed.

## Context

AgenticKVM has a dependency-free, mock-only MCP SDK adapter and host
compatibility layer. These prove local tool listing, schema generation, tool
calling, approval-required results, explicit approval resumption, audit
persistence, provider error normalization, artifact metadata safety, and
JSON-safe result serialization without a real MCP SDK dependency or live
server.

The next major MCP decision is whether to adopt a real MCP SDK and implement a
live MCP server adapter. That decision carries security risk because a live MCP
server may expose a local or remote interface, may add runtime dependencies,
may introduce transport-specific behavior, and may accidentally become a
provider bypass if treated as an authority boundary.

## Decision

Future live MCP server work must adapt to the existing host compatibility
contract. The live server is an interface adapter only. It is not an authority
boundary.

The required path remains:

```text
MCP host/client
-> live MCP server adapter
-> MCP host compatibility contract
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

No live MCP server will be implemented until dependency review, acceptance
gates, packaging review, audit-store review, host conformance testing, and
manual smoke planning are complete.

## Boundary Requirements

- No network listener by default.
- Prefer local stdio-first integration for the first live server trial, unless
  the accepted dependency review justifies a different local-only transport.
- Real providers remain disabled by default.
- Mock-only test mode is mandatory.
- The server must not call providers directly.
- The server must not bypass `MCPRouter`, registries, or `ControlPlane`.
- The server must not auto-approve.
- The server must preserve `approval_required` as a first-class result.
- Approval response submission and resumption must remain explicit and
  scope-bound.
- Audit persistence, audit failure behavior, checkpoints, exports, and
  retention requirements must be preserved.
- Provider error taxonomy and retryability must be preserved.
- Artifact metadata policy must be preserved; raw screenshots and raw bytes
  must not enter host results or audit logs.
- Credential references must remain redacted and unresolved by default.
- Tool arguments, provider payloads, secrets, credential refs, screenshots, and
  raw artifacts must not be logged by default.

## Why Not Implement Live Server Now

The current mock-only layer is intentionally stronger than an early live
server. It already proves safety-critical behavior without dependency,
transport, listener, credential, or provider risk. A live server would add
attack surface before the dependency and conformance gates are complete.

## Dependency Review Requirement

Before implementation, the selected candidate must pass:

- `docs/mcp-sdk-dependency-review.md`
- `docs/mcp-sdk-candidate-matrix.md`
- `specs/006-mcp-sdk-adapter/contracts/sdk-dependency-review.md`
- `docs/mcp-live-server-acceptance.md`
- `specs/006-mcp-sdk-adapter/contracts/live-server-acceptance-gate.md`

Unknown or failed evidence in authority routing, provider bypass, approval,
audit, secret handling, logging, or CI isolation blocks selection.

## Host Conformance Requirement

A future live server adapter must pass the existing mock-only host conformance
suite before merge:

- tool listing and schema generation
- unknown tool and unknown target fail-closed behavior
- disabled provider fail-closed behavior
- approval-required pass-through
- one-time and session approval resumption
- provider-error normalization
- audit persistence and hash-chain verification
- audit checkpoint/export verification
- audit failure fail-closed behavior
- artifact metadata redaction
- golden host result fixtures
- host result schema validation

## Production Audit-Store Gate

The live server cannot proceed to live provider exposure until production
audit-store requirements are acknowledged. At minimum, the integration must
preserve:

- redaction before persistence
- append-only event semantics
- hash-chain verification
- checkpoint-backed tail-truncation detection
- export/import verification
- audit failure signaling
- high-risk fail-closed behavior when audit is unavailable
- retention/rotation rules that reject silent deletion

## Manual Smoke Requirement

First live MCP server smoke testing must be manually approved, local-only, and
mock-provider-only. No real PiKVM, Redfish, BMC, remote desktop, or physical
host access is allowed through the server until a separate live provider gate is
accepted.

## Rollback Strategy

- Remove the live SDK dependency from the trial branch.
- Revert the live adapter while preserving dependency-review docs.
- Keep dependency-free host compatibility tests as the baseline.
- Keep real providers disabled and fixture-only.

## Consequences

This decision slows live MCP adoption, but it prevents the server layer from
quietly becoming the authority boundary. It also gives future implementation a
clear conformance target.

## Open Questions

- Which SDK candidate should be trialed first?
- Should first live transport be stdio-only?
- How should operator approval UI/transport integrate with MCP host clients?
- Which production audit backend is acceptable for public beta?
- Which smoke-test environment is acceptable for the first live server trial?
