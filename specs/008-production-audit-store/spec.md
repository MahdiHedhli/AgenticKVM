# Spec 008: Production Audit Store

## Status

Draft. This spec defines production audit-store requirements and local
mock-safe scaffolding. It does not implement a production backend, live MCP
server, live provider, live network path, or credential resolution.

## Problem

The current local JSONL audit sink provides redaction and a previous-hash chain.
It detects content tampering, middle-event deletion, and event reordering, but
it cannot detect tail truncation unless a trusted checkpoint records the last
known event hash and count outside the log.

Future live MCP servers and live providers need stronger audit requirements
before they can be trusted with real infrastructure.

## Goals

- append-only event history
- tamper evidence
- tail-truncation detection through checkpoints
- external checkpoint support
- redaction before persistence
- artifact metadata only, no raw sensitive bytes by default
- explicit audit path or store configuration
- fail-closed behavior for high-risk actions when audit is unavailable
- export/import verification
- retention and rotation policy
- operator-readable investigation workflow
- no secrets in audit logs
- no credentials in audit logs
- no raw screenshot bytes in audit logs
- no provider credentials or credential refs unless redacted

## Non-Goals

- external production service integration
- cloud storage backend
- SIEM integration
- real MCP SDK/server selection
- real MCP server implementation
- real provider implementation
- live hardware access
- live network access
- credential resolution

## User Stories

1. As an operator, I can verify that an audit log has not been modified or
   truncated since a checkpoint.
2. As an integrator, I can export an audit bundle and verify it offline without
   live services.
3. As a security reviewer, I can confirm audit exports contain no raw secrets,
   credential values, or raw screenshot bytes.
4. As a future MCP server author, I can see which audit behaviors must be
   preserved before live provider exposure.

## Acceptance Criteria

- Local checkpoint creation verifies a valid JSONL audit log.
- Checkpoint verification detects tail truncation after checkpoint.
- Checkpoint verification detects last-hash and event-count mismatches.
- Export/import verification detects tampering and malformed bundles.
- Retention policy rejects silent deletion and requires checkpoints or verified
  archives before rotation.
- Audit failure behavior is documented and covered by tests for high-risk
  actions.
- Host audit conformance fixtures cover ok, denied, approval, provider-error,
  artifact, checkpoint, export, and audit-failure paths.
- All tests remain mock-only, repo-local, and temp-path based.
