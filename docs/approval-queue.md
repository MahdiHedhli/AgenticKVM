# Approval Queue

The local approval queue is an explicit-path JSON store for operator approval
transport. It records pending approval requests and explicit operator decisions.

It is not an authority boundary and it does not execute providers.

## Path Requirement

The queue is active only when an operator supplies:

```bash
agentickvm --approval-path /tmp/agentickvm-approvals.json ...
```

Tests use temp directories. AgenticKVM does not create a global default approval
queue.

## Stored Binding

Each queued approval binds to:

- approval request id
- session id
- target id
- provider id
- capability id
- params fingerprint
- policy decision
- expiry
- operator id after decision
- one-time or session scope after approval

Mismatched parameters, target, provider, capability, session, expiry, or scope
fail closed.

## States

- `pending`
- `approved`
- `denied`
- `expired`
- `consumed`

One-time approvals become `consumed` after matching execution. Session approvals
remain `approved` and reusable only for the exact same binding.

## Audit Behavior

When an audit sink is configured:

- `approval_required` tool calls emit existing control-plane
  `approval_requested` events
- `approvals approve` emits `approval_granted`
- `approvals deny` emits `approval_denied`
- `approvals expire` emits `approval_expired`
- matching one-time execution emits existing control-plane `approval_consumed`

`approvals list` and `approvals show` are local read-only queue inspection
commands and do not currently emit audit events. If operator policy later
requires audited approval viewing, that should be added as a separate explicit
event type.

## Redaction

Approval params previews and decision reasons are redacted before persistence.
Raw secret-like parameter values must not appear in the queue file.

## Hard Invariants

The queue cannot grant hard-invariant capabilities such as:

- policy modification
- audit disabling
- emergency stop disabling
- raw secret reveal by default

Fabricated or malformed approval records fail closed.
