# Audit Retention And Rotation Policy

## Required Policy Fields

- policy id
- max event count
- max log bytes
- max age days
- rotation requires checkpoint
- rotation requires verified archive
- silent deletion setting
- archive metadata

## Rules

- Silent deletion is rejected by default.
- Rotation must require a checkpoint or verified archive.
- Rotation must not erase evidence before verification.
- Agent-triggered audit deletion is not allowed without explicit policy.
- Archive metadata must be JSON-safe and redacted.
- Retention policy must not permit raw secrets or raw artifact bytes.

## Deferred Production Decisions

- legal retention period
- archive backend
- immutable storage backend
- external checkpoint signer
- operator approval workflow for deletion
