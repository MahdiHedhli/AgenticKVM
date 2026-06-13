# Operator Approval

## Current Direction: ACT Clearance

AgenticKVM now consumes clearance from Agentic Control Tower (ACT). ACT owns the
production clearance contract, signing, mobile approval, operator channel, replay
defense, one-time clearance consumption, and tower-side clearance audit.

AgenticKVM owns capability resolution, local policy, provider and target safety,
provider execution, local audit, and fail-closed behavior. It does not duplicate
ACT broker crypto and does not author the clearance wire contract.

The local signed-grant broker work described below is superseded for production
authority. It may remain as dev/test scaffold and as regression coverage proving
that editable local files are not authority. Production clearance comes from ACT.

Operator approval is required when policy returns `ask_each_time` or
`ask_once_per_session`.

## Approval Prompt Requirements

An approval prompt must explain:

- requested capability and action
- affected target scope
- active session scope
- requester identity
- policy decision that caused the prompt
- material risks
- expected provider effect
- approval duration
- audit event that will be recorded

## Approval Decisions

### ask_each_time

The operator must approve every matching request.

### ask_once_per_session

The operator may approve a matching capability, target scope, and parameter
shape for the active session. Reuse must be audited and must not silently expand
scope.

## Approval Resumption

The current implementation supports an in-memory, mock-only approval resumption
model for tests and bootstrap flows. A grant is tied to:

- approval request id
- approval response id
- session id
- target id
- provider id
- capability id
- parameter fingerprint
- expiration time
- one-time or session scope

One-time grants are consumed after one matching execution. Session grants can be
reused only for the same session, target, provider, capability, and parameter
fingerprint. Consumed approvals emit an `approval_consumed` audit event.

## Local Approval Transport

The CLI also supports an explicit local approval queue through
`--approval-path`. See [Local Operator Approval Transport](operator-approval-transport.md).
Queue storage and state details are in [Approval Queue](approval-queue.md).

The local queue records `approval_required` results, lets an operator list,
show, approve, deny, or expire requests, and converts approved records into the
existing `ApprovalStore` only when a later CLI call is made with the same
explicit queue path.

This transport does not execute providers during approval submission and does
not auto-approve. Resumed actions still route through `MCPRouter`, registries,
policy, audit, and `ControlPlane`.

## Approval Cannot Grant

Approval cannot grant capabilities outside policy, change hard invariants,
disable audit, disable emergency stop, reveal secrets by default, or add targets
outside session scope.

## Dangerous Actions

Dangerous actions in Supervised mode require explainable approval and explicit
scope. Approval text must not hide material risk.

## MCP SDK Adapter

The mock-only MCP SDK adapter preserves `approval_required` results from the
existing MCP router. It does not auto-approve, resume approvals, or create
approval grants.

Future live SDK/server adapters must preserve the same behavior: approval is a
first-class result returned to the caller, not permission to continue
execution.

## MCP Host Compatibility

The mock-only MCP host compatibility layer models approval response submission
and approved-action resumption for local tests. It remains dependency-free and
does not open a live server.

Host-level approval responses must match the original approval request by
request id, session id, target id, provider id, capability id, parameter
fingerprint, scope, and expiry. A mismatch fails closed.

One-time approvals are consumed after one matching resumed execution. Session
approvals may be reused only for the same session, target, provider,
capability, and parameter fingerprint.

Host approval submission must audit granted, denied, or expired responses.
Control-plane execution must audit approval consumption and provider execution
when a resumed action is actually allowed to run.

The host layer cannot auto-approve and cannot use approval to bypass hard
invariants such as policy modification, audit disabling, emergency stop
disabling, target expansion, provider expansion, or raw secret reveal by
default.

Approved resumption remains a normal control-plane request. The host does not
call providers directly and does not execute during approval submission.

Approval grants are stored only after the approval-granted audit event is
successfully emitted. If audit persistence fails, approval submission fails
closed and the grant is not usable. Approved resumption also fails closed when
required audit emission fails before provider execution.

## Superseded Local Approval Broker Direction

The local approval queue is not an authority model. The previous AgenticKVM
Approval Broker v1 signed-grant direction is superseded by ACT for production
clearance authority. File-backed storage is cache/UX state only.

MCP may request clearance or deny clearance. MCP must never grant, approve,
clear, sign, or trust a clearance.

## Local Broker CLI Surface Is Dev/Test Only

Approval Broker v1 adds an operator-facing signed-cache surface:

```bash
agentickvm --broker-cache-path /explicit/temp/path/approvals.json approvals watch
agentickvm --broker-cache-path /explicit/temp/path/approvals.json approvals allow <request-id> \
  --operator-id <operator> \
  --session-id <session> \
  --target <target> \
  --provider <provider> \
  --capability <capability> \
  --params-fingerprint <fingerprint> \
  --risk-family <family> \
  --expires-at <timestamp> \
  --dev-signer
agentickvm --broker-cache-path /explicit/temp/path/approvals.json approvals deny <request-id> \
  --operator-id <operator>
```

The `allow` command is an operator surface, not an MCP tool. In this branch it
uses a development/test HMAC signer only when `--dev-signer` is explicit. That
signer is useful for local tests and compatibility checks, but it is not a
production trust anchor if the agent can read the key material. Production
clearance authority is ACT.

The signed cache is written with explicit paths, atomic replacement, advisory
locking, and `0600` file mode. The cache remains non-authoritative: editing the
file cannot grant approval unless the signature and exact request binding still
verify.
