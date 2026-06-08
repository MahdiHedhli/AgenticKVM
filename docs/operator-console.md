# Local Operator Console

AgenticKVM includes a local CLI status console for operator visibility. It is
not a web console and does not open a network listener.

```bash
agentickvm status
```

or:

```bash
agentickvm console
```

When an approval queue or audit log is configured explicitly, include:

```bash
agentickvm --approval-path /tmp/agentickvm-approvals.json \
  --audit-path /tmp/agentickvm-audit.jsonl \
  status
```

## Output

The status payload reports:

- active policy mode
- configured provider summaries
- configured target summaries
- pending local approvals
- audit path configuration
- audit hash-chain verification result when an audit path is supplied
- live provider default status
- network listener status

## Safety Boundary

The console is read-only. It does not:

- execute providers
- resolve credentials
- read environment secrets
- start a server
- open a TCP/HTTP/WebSocket listener
- enable live providers
- auto-approve pending requests

Provider and target details come from the explicit runtime registries. Pending
approvals come only from the operator-supplied local approval queue path.

## Current Limitations

The first console is JSON output intended for local operators, tests, and CI
logs. A richer TUI or browser console remains deferred until it can be added
without changing exposure boundaries or creating an always-on listener.
