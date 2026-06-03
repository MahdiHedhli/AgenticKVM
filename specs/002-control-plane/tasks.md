# Tasks: Control Plane

## Contract Tasks

- [x] Add policy schema.
- [x] Add capability registry schema.
- [x] Add approval request schema.
- [x] Add audit event schema.
- [x] Add provider contract document.

## Bootstrap Code Tasks

- [x] Add documented constants for modes, decisions, capability families,
  dangerous actions, and invariants.
- [x] Add abstract base provider interface.
- [x] Add safe mock provider placeholder.
- [x] Add import and safety tests.

## Policy Engine Tasks

- [ ] Implement policy document loader.
- [ ] Implement capability registry loader.
- [ ] Implement default-deny unknown capability path.
- [ ] Implement explicit scope matching.
- [ ] Implement dangerous action handling.
- [ ] Implement limit evaluation.
- [ ] Add policy decision tests for each mode.

## Approval Tasks

- [ ] Implement approval request builder.
- [ ] Implement approval store.
- [ ] Implement `ask_each_time`.
- [ ] Implement `ask_once_per_session`.
- [ ] Add approval expiration tests.

## Audit Tasks

- [ ] Implement audit event writer.
- [ ] Implement secret redaction.
- [ ] Add audit event contract tests.
- [ ] Add tests proving audit cannot be disabled by agent request.

## Interface Tasks

- [ ] Add CLI request path through control plane.
- [ ] Add MCP request path through control plane.
- [ ] Add tests proving interfaces do not call providers directly.

## Provider Tasks

- [ ] Expand mock provider fixtures.
- [ ] Add PiKVM provider spec before implementation.
- [ ] Add Redfish provider spec before implementation.
- [ ] Add opt-in lab-only provider integration tests outside CI.
