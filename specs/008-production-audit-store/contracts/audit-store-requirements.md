# Audit Store Requirements

## Required Properties

- append-only event history
- redaction before persistence
- structured JSON-safe records
- tamper-evident hash chaining
- tail-truncation detection through checkpoints
- explicit audit path or store configuration
- no raw secrets
- no raw credentials
- no unredacted credential refs
- no raw screenshot bytes
- no raw artifact bytes
- provider result metadata only unless explicitly scoped
- export/import verification
- retention and rotation policy
- operator-readable investigation workflow

## Failure Behavior

High-risk actions must fail closed when required audit persistence is
unavailable. Audit failure must not be silently swallowed and must not allow
provider execution without an audit event when audit is required.

## Current Scope

The current implementation is local JSONL plus checkpoints and export
verification helpers. Production backends remain deferred.
