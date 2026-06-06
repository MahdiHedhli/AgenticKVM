# Operator Approval

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

## Future In-Band Provider Risks

For future RustDesk, VNC, RDP, MeshCentral, BrowserBridge, or desktop/session
providers, the following actions require explicit capability mapping and
explainable approval before implementation:

- keyboard and mouse control
- clipboard read or write
- file transfer
- remote command execution
- remote access agent install, update, or settings changes
- privilege escalation
- unattended control of production desktops
- screenshot or stream capture when policy requires approval

Approval must state whether the OS user is expected to be notified or involved
when environment policy requires consent.
