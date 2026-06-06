# Audit Store

AgenticKVM treats audit as mandatory evidence. The current implementation uses
a local JSONL audit sink for mock and fixture workflows, plus an explicit-path
SQLite audit backend v1 for local persistence experiments.

No cloud storage backend, SIEM integration, live MCP server, live provider,
credential resolution, or live network path exists yet.

## Current Local JSONL Sink

`LocalJSONLAuditSink` writes redacted JSONL records to an explicitly configured
file path. Each record contains:

- `previous_hash`
- redacted `event`
- `event_hash`

This hash chain detects content tampering, middle-event deletion, and event
reordering.

## Local SQLite Backend V1

`SQLiteAuditSink` stores redacted audit records in a local SQLite database at
an explicitly configured path. It uses the Python standard library only.

The SQLite table stores:

- event index
- previous hash
- event hash
- redacted event JSON

The SQLite backend preserves the same hash-chain semantics as JSONL and can be
verified with:

```bash
agentickvm audit verify --sqlite-path /tmp/agentickvm-audit.sqlite
```

Recent events can be listed with:

```bash
agentickvm audit list --sqlite-path /tmp/agentickvm-audit.sqlite
```

Single events can be inspected with:

```bash
agentickvm audit inspect --sqlite-path /tmp/agentickvm-audit.sqlite --event-index 1
```

SQLite checkpoints can be written to an explicit JSON path:

```bash
agentickvm audit checkpoint \
  --sqlite-path /tmp/agentickvm-audit.sqlite \
  --audit-log-id local-operator-run \
  --output /tmp/agentickvm-audit-checkpoint.json
```

Exports require an explicit output path:

```bash
agentickvm audit export \
  --sqlite-path /tmp/agentickvm-audit.sqlite \
  --output /tmp/agentickvm-audit-export.json
```

Runtime use is opt-in:

```bash
agentickvm --audit-sqlite-path /tmp/agentickvm-audit.sqlite status
```

The SQLite backend does not enable live providers, open network connections,
resolve credentials, or change policy behavior. Tests use temp directories
only.

Hardening details and known limitations are tracked in
[SQLite Audit Backend Hardening](sqlite-audit-hardening.md).
Command details are in [Audit CLI](audit-cli.md).

## Tail-Truncation Risk

A hash chain alone cannot detect an attacker removing records from the end of
the log. Tail-truncation detection requires a checkpoint stored outside the
audit log.

`AuditCheckpoint` records:

- checkpoint id
- audit log id
- last event index
- event count
- last event hash
- creation timestamp
- optional previous checkpoint hash
- redacted metadata
- checkpoint hash

Verification fails closed when the log has fewer events than the checkpoint,
the checkpointed event hash changed, the event count is inconsistent, the chain
is malformed, or the checkpoint hash does not match its content.

Appending events after a checkpoint is allowed. Truncating events at or before
the checkpoint is not allowed.

SQLite audit checkpoints use the same model through
`create_sqlite_audit_checkpoint` and `verify_sqlite_audit_checkpoint`.

## Export And Import Verification

`export_audit_log` returns a JSON-safe in-memory bundle containing:

- export metadata
- redacted records
- optional checkpoint
- chain verification summary
- checkpoint verification summary
- record count
- last event hash
- redaction summary

`verify_audit_export` validates structure, hash chain, checkpoint, record count,
last hash, and malformed bundle behavior.

Exports must not contain raw secrets, raw credentials, unredacted credential
refs, raw screenshot bytes, raw image fields, or raw provider credentials.

## Retention And Rotation

`AuditRetentionPolicy` is a validation model only. It does not delete, rotate,
archive, or write audit logs.

Rules:

- silent audit deletion is rejected
- rotation must require a checkpoint or verified archive
- archive metadata is redacted
- deletion/rotation must not erase evidence before verification
- agent-triggered audit deletion remains disallowed without explicit policy

Production retention period, archive backend, immutable storage, checkpoint
signing, and operator deletion workflow remain deferred.

## Failure Behavior

Audit failure must not create an unaudited provider execution path.

Current behavior is fail closed:

- read-only host calls fail closed by default when audit emits fail
- dangerous actions fail closed before provider execution
- approval grants are stored only after approval-granted audit emits succeed
- approved resumption fails closed if required audit emits fail
- host results surface structured, redacted `policy_error` payloads for
  control-plane audit failures

Future production policy may define selected warning-only read-only behavior,
but no such behavior exists today.

## Host Conformance

Host audit conformance fixtures cover:

- ok action audit lifecycle
- denied action audit lifecycle
- approval-required lifecycle
- approval granted and consumed lifecycle
- provider-error lifecycle
- artifact metadata lifecycle
- checkpoint verification lifecycle
- export verification lifecycle
- audit failure lifecycle

Future live MCP servers must pass these fixtures before exposing live provider
work.

## MCP SDK Dependency Gate

A future live MCP SDK/server dependency is acceptable only if an SDK-backed
adapter preserves the current audit behavior:

- audit writes remain explicit and redacted
- audit failure remains structured and fail-closed for high-risk actions
- approval lifecycle events are emitted before approval grants are stored or
  consumed
- provider execution and provider errors remain auditable
- artifact metadata is audit-safe and contains no raw bytes
- checkpoint-backed tail-truncation detection still verifies
- export/import verification still detects tampering and malformed bundles
- CI tests remain mock-only and use temporary audit paths

The SDK must not log raw tool arguments, secrets, credential refs,
screenshots, raw artifact bytes, or raw provider payloads as a substitute for
AgenticKVM audit.

## Future Production Options

Options to evaluate later:

- local append-only file with external checkpoint
- external checkpoint file
- OS-protected append-only storage
- database-backed audit store
- object storage with versioning or retention lock
- SIEM/export pipeline
- externally signed checkpoints

## Deferred

- cloud/SIEM integration
- checkpoint signing
- production retention period
- production audit-store access control
- production database hardening and locking policy
- live MCP server integration
- live provider integration
