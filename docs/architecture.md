# Architecture

AgenticKVM is a spec-driven control plane for safe agentic out-of-band
infrastructure operations.

## Authority Boundary

Policy is the authority boundary. Interfaces and providers are not.

All action paths must follow:

1. agent/tool request
2. capability request
3. policy decision
4. operator approval if required
5. provider adapter
6. structured audit event
7. result

## Layers

### Interface Layer

Future MCP tools, CLI commands, API handlers, and agent workflows live here.
Their job is to describe intent and submit capability requests to the control
plane. They must not import or call provider adapters directly.

### Control Plane

The control plane resolves capabilities, evaluates policy, asks for approval,
calls providers, records audit events, and returns structured results.

### Policy Engine

The policy engine evaluates visible mode, capability registry entries, target
scope, session scope, limits, dangerous action flags, and hard invariants.
Unknown capabilities return `deny`.

### Approval Broker

The approval broker creates explainable operator prompts for decisions such as
`ask_each_time` and `ask_once_per_session`.

### Audit Writer

The audit writer records every request state. Audit is mandatory and secrets are
redacted by default.

### Provider Adapters

Provider adapters translate authorized provider-neutral requests into
provider-specific operations. They do not own policy.

## Current Bootstrap State

The current implementation includes only:

- documented constants
- base provider contract
- safe mock provider
- offline tests

Real provider implementations are deferred until the control plane, policy
engine, approvals, audit, and mock tests are in place.

## Design Rule

If a component can touch real infrastructure, it must be reachable only through
the control plane and only after policy and approval requirements have been
satisfied.
