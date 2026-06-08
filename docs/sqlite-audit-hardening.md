# SQLite Audit Backend Hardening

`SQLiteAuditSink` is AgenticKVM's local audit backend v1. It is intended for
public beta readiness and local operator workflows, not as a complete external
production audit service.

## Current Schema

The backend creates one table:

```sql
CREATE TABLE IF NOT EXISTS audit_events (
  event_index INTEGER PRIMARY KEY AUTOINCREMENT,
  previous_hash TEXT,
  event_hash TEXT NOT NULL,
  event_json TEXT NOT NULL
)
```

`event_json` contains the same redacted record shape as the JSONL audit sink:

- `previous_hash`
- redacted `event`
- `event_hash`

The table columns duplicate `previous_hash` and `event_hash` so verification
can detect mismatches between the indexed row metadata and serialized record.

## Explicit Path Requirement

SQLite audit writes require an operator-supplied path such as
`--audit-sqlite-path /tmp/agentickvm-audit.sqlite`. AgenticKVM does not create a
global default audit database.

Tests use temp directories only.

## Redaction Before Write

Audit events are redacted before insertion. The backend reuses the same
redaction behavior as the JSONL sink for request, result, and approval payloads.

The backend must not persist:

- raw secrets
- raw provider credentials
- unredacted credential material
- raw screenshot bytes
- raw artifact bytes
- raw exception objects

## Hash Chain

Each inserted event signs:

- previous event hash
- redacted event payload

Verification checks:

- table previous hash
- serialized record previous hash
- table event hash
- serialized record event hash
- recomputed hash

Content tampering, middle-event deletion, row reordering, and row/record hash
mismatch fail verification.

## Checkpoints

SQLite checkpoints reuse the existing `AuditCheckpoint` model.

`create_sqlite_audit_checkpoint` records:

- checkpoint id
- audit log id
- logical event count
- logical last event index
- last event hash
- created timestamp
- redacted metadata

`verify_sqlite_audit_checkpoint` detects tail truncation at or before the
checkpoint, last-event hash mismatch, malformed checkpoints, and malformed
audit stores.

## Export And Investigation

The SQLite backend supports:

- `agentickvm audit verify --sqlite-path <path>`
- `agentickvm audit list --sqlite-path <path>`
- `agentickvm audit export --sqlite-path <path> --output <path>`

Exports can include a verified checkpoint. Operators should export before
rotation, backup, or external retention.

## Failure Behavior

Malformed SQLite files, missing tables, invalid event JSON, bad hashes, and
checkpoint mismatches fail closed through structured verification failures or
`SQLiteAuditError`.

Provider execution must not treat audit write or verification failure as
success.

## Concurrency Assumptions

SQLite provides local file locking, but this v1 backend assumes a small number
of local AgenticKVM processes. High-concurrency production use needs a separate
review of transaction isolation, WAL mode, backup behavior, and operator access
controls.

## File Permissions Guidance

Operators should store SQLite audit files in a restricted local directory and
use OS-level permissions appropriate for audit evidence. AgenticKVM does not
currently manage file ownership, chmod, encryption, signing, or external
retention.

## Known Limitations

- no external signing
- no external checkpoint service
- no SIEM integration
- no cloud/object store backend
- no retention lock
- no encrypted database support
- no production access-control layer
- no automatic backup or rotation

## Not-Yet-Production Requirements

Before calling this a production audit backend, the project needs a human
review of:

- external checkpoint strategy
- backup/export workflow
- retention and deletion policy
- file permissions and local OS hardening
- corruption recovery
- concurrent writer behavior
- release packaging of audit tools
- operator incident/investigation workflow
