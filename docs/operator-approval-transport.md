# Local Operator Approval Transport

AgenticKVM now includes a local, file-backed approval queue for operator
workflows. This is a local transport, not an authority boundary.

The approval queue records approval-required actions and explicit operator
decisions for local operator workflow. It does not grant execution authority.
Approval authority now comes from broker-owned signed grants verified by the
control plane.

## Scope

Allowed:

- explicit local approval queue path
- explicit local audit path
- pending approval listing
- pending approval detail
- approve, deny, and expire decisions
- request/decision cache semantics
- exact-action binding previews for operator review
- migration aid while Approval Broker v1 becomes the authority path

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

The queue records the binding that a signed broker grant must later satisfy:

- approval request id
- session id
- target id
- provider id
- capability id
- params fingerprint
- expiry
- operator id
- scope

The queue does not convert approved records into executable grants. Editing the
queue file, or marking an entry approved, cannot authorize provider execution.
The operator must use a broker signer, such as the Approval Broker CLI
`approvals allow` command in development mode or a future production trust
anchor.

## One-Time And Session Scope

Queue records can still show intended one-time or session scope for operator
review, but that scope is informational in the file-backed queue. One-time
consumption and session reuse are enforced by signed broker grants and the
control-plane verifier.

Denied, expired, and mismatched queue records cannot authorize execution.

## Audit

When `--audit-path` is supplied:

- approval-required tool calls emit existing control-plane audit events
- approval decisions emit `approval_granted`, `approval_denied`, or
  `approval_expired`
- signed broker grant consumption emits `approval_consumed` events
- audit writes use the existing local JSONL hash chain

Audit data is redacted before persistence. Raw secrets, credential material,
and raw screenshot bytes must not be written to the queue or audit log.

## Safety Notes

The local approval queue is a convenience transport for operator workflows. It
does not relax policy, target scope, provider scope, emergency stop, audit, or
hard-invariant rules.

The queue is disabled unless an operator supplies `--approval-path`.
Automated tests use temp directories only.
