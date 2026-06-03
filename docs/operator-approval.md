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

## Approval Cannot Grant

Approval cannot grant capabilities outside policy, change hard invariants,
disable audit, disable emergency stop, reveal secrets by default, or add targets
outside session scope.

## Dangerous Actions

Dangerous actions in Supervised mode require explainable approval and explicit
scope. Approval text must not hide material risk.
