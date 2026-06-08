# Local Operator Approval Transport

AgenticKVM now includes a local, file-backed approval queue for operator
workflows. This is a local transport, not an authority boundary.

The approval queue records approval-required actions, explicit operator
decisions, and enough exact-action binding data to resume approved mock flows
through the existing MCP router and `ControlPlane`.

## Scope

Allowed:

- explicit local approval queue path
- explicit local audit path
- pending approval listing
- pending approval detail
- approve, deny, and expire decisions
- one-time approval consumption
- session-scoped approval reuse
- mock and fixture-only resumption through `ControlPlane`

Disallowed:

- auto-approval
- provider execution during approval submission
- credential resolution
- environment secret reads
- direct provider execution
- live provider enablement
- live hardware smoke
- approval of hard invariants

## CLI

All commands require an explicit approval queue path:

```bash
agentickvm --approval-path /tmp/agentickvm-approvals.json call \
  --target mock-host \
  --tool force_restart \
  --session-id operator-session \
  --param reason=maintenance

agentickvm --approval-path /tmp/agentickvm-approvals.json approvals list

agentickvm --approval-path /tmp/agentickvm-approvals.json approvals show <approval-id>

agentickvm --approval-path /tmp/agentickvm-approvals.json approvals approve <approval-id> \
  --operator-id operator-1 \
  --scope one_time \
  --reason "approved for test"

agentickvm --approval-path /tmp/agentickvm-approvals.json approvals deny <approval-id> \
  --operator-id operator-1 \
  --reason "not safe now"

agentickvm --approval-path /tmp/agentickvm-approvals.json approvals expire <approval-id> \
  --operator-id operator-1 \
  --reason "window closed"
```

Add `--audit-path /tmp/agentickvm-audit.jsonl` to persist local JSONL audit
events for the same flow.

## Binding

An approved record is bound to:

- approval request id
- session id
- target id
- provider id
- capability id
- params fingerprint
- expiry
- operator id
- scope

A matching approved record is converted into the existing in-memory
`ApprovalStore` when the CLI runtime is built. The resumed action is then a
normal MCP tool call routed through `MCPRouter`, target/provider registries,
policy, approval checks, audit, and `ControlPlane`.

## One-Time And Session Scope

One-time approval records are marked `consumed` after a matching successful or
provider-error resumed execution. This mirrors the control-plane behavior:
approval is consumed before provider execution.

Session approval records remain `approved`, but only match the same session,
target, provider, capability, params fingerprint, and unexpired time window.

Denied, expired, consumed, and mismatched approvals fail closed.

## Audit

When `--audit-path` is supplied:

- approval-required tool calls emit existing control-plane audit events
- approval decisions emit `approval_granted`, `approval_denied`, or
  `approval_expired`
- resumed one-time execution emits existing `approval_consumed` events
- audit writes use the existing local JSONL hash chain

Audit data is redacted before persistence. Raw secrets, credential material,
and raw screenshot bytes must not be written to the queue or audit log.

## Safety Notes

The local approval queue is a convenience transport for operator workflows. It
does not relax policy, target scope, provider scope, emergency stop, audit, or
hard-invariant rules.

The queue is disabled unless an operator supplies `--approval-path`.
Automated tests use temp directories only.
