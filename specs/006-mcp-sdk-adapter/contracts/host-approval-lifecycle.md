# MCP Host Approval Lifecycle Contract

## Status

Mock-only contract for local host compatibility tests. This is not a live MCP
server or approval transport contract.

## Purpose

A future MCP host must preserve AgenticKVM approval semantics when an MCP tool
returns `approval_required`. Approval is a separate operator-controlled step,
not implicit permission to execute.

This contract defines how the dependency-free host compatibility layer models
approval requests, approval responses, approved-action resumption, and audit
persistence before any real MCP SDK/server dependency is added.

## Required Lifecycle

1. Host calls a tool.
2. SDK adapter and MCP router route the request through `ControlPlane`.
3. Policy returns `ask_each_time` or `ask_once_per_session`.
4. Host receives `approval_required`.
5. Host serializes approval request metadata.
6. Operator or explicit test fixture submits an approval response.
7. Host validates the response against the pending request.
8. Matching action may be resumed through the same host/adapter/router/control
   plane path.
9. Approval is consumed or retained according to scope.
10. Audit records approval requested, granted or denied or expired, consumed,
    provider execution if any, and final result.

## Approval Binding

An approval response must bind to:

- approval request id
- session id
- target id
- provider id
- capability id
- stable action fingerprint derived from safe parameters
- approval scope
- expiry/TTL
- operator decision

Approval for one target cannot approve another target. Approval for one
provider cannot approve another provider. Approval for one capability cannot
approve another capability. Approval for one parameter fingerprint cannot
approve a materially different action.

## Approval Scope

`one_time` approval is consumed by the first matching resumed execution.

`session` approval may be reused only within the exact same session, target,
provider, capability, and parameter fingerprint until it expires.

## Failure Rules

- unknown approval request ids fail closed
- malformed approval responses fail closed
- provider mismatch fails closed
- target mismatch fails closed
- capability mismatch fails closed
- session mismatch fails closed
- parameter fingerprint mismatch fails closed
- expired approval fails closed
- denied approval fails closed
- host cannot auto-approve

## Hard Invariants

Approval cannot bypass hard invariants. Approval cannot authorize:

- active policy modification
- audit disabling
- emergency stop disabling
- raw secret reveal by default
- silent target expansion
- silent provider expansion
- any action outside policy and session scope

## Audit Requirements

The host compatibility layer must preserve audit behavior:

- approval requested is emitted by `ControlPlane`
- approval granted, denied, or expired is emitted when a response is submitted
- approval consumed is emitted by `ControlPlane` before resumed execution
- provider execution events are emitted only if execution occurs
- denied and approval-required outcomes remain auditable
- JSONL audit persistence must remain hash-chain verifiable
- secret-shaped values and credential references must be redacted
- raw screenshot or stream bytes must not be written to audit

## Future Live MCP Server Gate

A future live MCP server must prove this same lifecycle with mock providers
before exposing live providers. It must not create approvals automatically,
resolve credentials by default, or start live-provider execution outside the
control-plane path.
