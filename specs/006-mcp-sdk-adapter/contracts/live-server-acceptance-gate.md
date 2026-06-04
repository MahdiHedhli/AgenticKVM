# Live MCP Server Acceptance Gate

## Status

Proposed. This gate must pass before AgenticKVM adopts a live MCP SDK/server
adapter.

## Before Implementation

- Dependency review framework is complete.
- Candidate matrix is complete.
- Live MCP server boundary ADR is accepted or explicitly updated.
- Host compatibility contract is current.
- Host approval lifecycle contract is current.
- Production audit-store requirements are reviewed.
- Packaging and supply-chain review is complete.
- Mock-only adapter plan is written.
- Rollback plan is written.
- No real providers are enabled by default.
- No network listener is selected without explicit architecture review.
- No credential resolution path is required for mock-only tests.

## Before Merge

- All tests pass.
- SDK-backed adapter uses the host compatibility path or a proven equivalent.
- Tool calls cannot bypass `MCPRouter`.
- Tool calls cannot bypass provider/target/capability registries.
- Tool calls cannot bypass `ControlPlane`.
- No provider is called directly by the live server.
- No auto-approval behavior exists.
- `approval_required` is preserved.
- Explicit approval response submission is preserved.
- One-time and session approval resumption remain scope-bound.
- `audit_error` or equivalent audit failure signaling is preserved.
- Audit failure fail-closed behavior is preserved for high-risk actions.
- Provider error taxonomy is preserved.
- Artifact metadata policy is preserved.
- Structured errors remain redacted.
- Tool schemas contain no secrets, real hosts, or raw provider internals.
- Output redaction is preserved.
- No raw tool arguments, secrets, screenshots, provider payloads, or credential
  references are logged by default.
- CI remains mock-only and cannot reach live providers.
- Dependency version or version strategy is documented.
- Dependency tree and optional extras are reviewed.
- Manual smoke docs are updated.

## Before First Live Use

- Operator approval is recorded.
- Transport exposure decision is recorded.
- Local-only mode is configured unless explicitly approved otherwise.
- Audit path or production audit store is configured.
- Audit checkpoint/export decision is acknowledged.
- Credential strategy is selected and credential references remain unresolved in
  repo config.
- Real providers remain disabled unless explicitly configured for the approved
  smoke scope.
- Manual smoke plan is executed against mock provider first.
- No live provider can be reached from CI.
- Rollback path is verified.

## Required Evidence

The acceptance gate must be backed by:

- dependency review document
- candidate matrix
- ADR
- host conformance test results
- audit-store conformance test results
- packaging/supply-chain notes
- updated security docs
- updated roadmap
- updated manual smoke docs

## Failure Handling

If any authority-routing, approval, audit, secret-handling, provider-bypass, or
CI-isolation requirement fails, the live server work must stop. The dependency
may remain under review, but it cannot be selected or added.
