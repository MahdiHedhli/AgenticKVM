# SQLite Audit Backend V1 Contract

Status: Draft

## Scope

The SQLite audit backend v1 is a local, explicit-path audit store for
AgenticKVM mock, fixture, and future operator-approved local workflows.

It does not implement an external production audit service.

## Required Properties

- uses an explicit operator-supplied path
- creates no global default database
- uses the Python standard library only
- redacts audit payloads before write
- stores no raw secrets or raw artifact bytes
- stores hash-chained records
- verifies hash chain after reopen
- supports checkpoint creation and verification
- supports explicit-path export
- fails closed on malformed stores
- exposes JSON-safe CLI results

## Schema

The backend must store:

- logical event index
- previous hash
- event hash
- serialized redacted event record

The serialized record must contain enough data to verify the hash without
trusting table columns alone.

## Checkpoint Contract

SQLite checkpoints must use the shared `AuditCheckpoint` model and bind to:

- audit log id
- logical event count
- logical last event index
- last event hash
- checkpoint hash

Verification must fail when:

- the SQLite chain is malformed
- the store has fewer events than the checkpoint
- the checkpointed event hash changed
- checkpoint content is malformed

## Export Contract

SQLite export must:

- require an explicit output path
- verify the chain before export
- include verification summary
- include event count
- include optional checkpoint and checkpoint verification status
- remain JSON-safe
- exclude raw secrets and raw artifact bytes

## Deferred Requirements

- external signing
- external checkpoint persistence
- cloud/SIEM export
- retention lock
- encrypted DB support
- production access-control model
- high-concurrency writer policy
