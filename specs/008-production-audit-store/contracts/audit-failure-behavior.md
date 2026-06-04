# Audit Failure Behavior

## Principle

Audit is mandatory. Audit failures must be visible, structured, redacted, and
must not create an unaudited provider execution path.

## High-Risk Actions

High-risk or approval-gated actions must fail closed if required audit
persistence is unavailable.

Examples include:

- force power actions
- boot override
- media mount
- raw secret reveal attempts
- policy modification attempts
- approval consumption
- provider execution for dangerous capabilities

## Low-Risk Actions

The default behavior is still fail closed until a later production policy
explicitly defines warning-only behavior for selected read-only actions.

## Required Result Behavior

Audit failure must produce a structured error. The result must not leak
secrets, raw exception details, credential refs, or raw artifact bytes.

## Prohibited Behavior

- swallowing audit failures silently
- provider execution after a required audit event fails
- approval consumption without audit
- falling back to unaudited execution
- disabling audit from an agent request
