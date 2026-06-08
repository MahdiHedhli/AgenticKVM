# Audit CLI

AgenticKVM audit commands are local, explicit-path commands for JSONL and
SQLite audit stores. They do not contact live providers, resolve credentials,
or read environment secrets.

## Verify

Verify a JSONL audit chain:

```bash
agentickvm audit verify --jsonl-path /tmp/agentickvm-audit.jsonl
```

Verify a SQLite audit chain:

```bash
agentickvm audit verify --sqlite-path /tmp/agentickvm-audit.sqlite
```

Verification returns `ok` for a valid chain and `audit_error` for a malformed
or tampered chain.

## List

List recent SQLite audit events:

```bash
agentickvm audit list --sqlite-path /tmp/agentickvm-audit.sqlite --limit 20
```

Output is JSON-safe and redacted.

## Inspect

Inspect one SQLite audit event by logical index:

```bash
agentickvm audit inspect --sqlite-path /tmp/agentickvm-audit.sqlite --event-index 1
```

or by event hash:

```bash
agentickvm audit inspect --sqlite-path /tmp/agentickvm-audit.sqlite --event-hash <hash>
```

Exactly one identifier is required.

## Checkpoint

Create a local SQLite checkpoint:

```bash
agentickvm audit checkpoint \
  --sqlite-path /tmp/agentickvm-audit.sqlite \
  --audit-log-id local-operator-run \
  --output /tmp/agentickvm-audit-checkpoint.json
```

The checkpoint binds to event count and last event hash for tail-truncation
detection.

## Export

Export a verified SQLite audit bundle:

```bash
agentickvm audit export \
  --sqlite-path /tmp/agentickvm-audit.sqlite \
  --output /tmp/agentickvm-audit-export.json
```

Export with a checkpoint:

```bash
agentickvm audit export \
  --sqlite-path /tmp/agentickvm-audit.sqlite \
  --checkpoint-path /tmp/agentickvm-audit-checkpoint.json \
  --output /tmp/agentickvm-audit-export.json
```

Export fails closed when chain or checkpoint verification fails.

## Safety

Audit CLI commands require explicit paths. Tests use temp directories only.
Generated audit databases, checkpoints, and exports must not be committed.
