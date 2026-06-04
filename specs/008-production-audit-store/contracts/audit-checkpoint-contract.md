# Audit Checkpoint Contract

## Purpose

Audit checkpoints provide tail-truncation detection by storing the last known
event count and last event hash outside the audit JSONL log.

## Required Fields

- checkpoint id
- audit log id
- last event index
- event count
- last event hash
- created timestamp
- optional previous checkpoint hash
- redacted metadata
- checkpoint hash

## Verification

Checkpoint verification must fail closed when:

- audit log is malformed
- audit chain fails
- event count is lower than the checkpoint count
- checkpointed event hash does not match the event at the checkpoint index
- checkpoint metadata is malformed
- checkpoint hash does not verify

Appending events after a checkpoint is allowed. Truncating events at or before
the checkpoint is not allowed.

## Safety

Checkpoint metadata is redacted before serialization. Checkpoints must not
contain raw secrets, raw credentials, credential values, or raw artifact bytes.
