# Architecture

AgenticKVM is a spec-driven control plane for safe agentic out-of-band
infrastructure operations.

## Authority Boundary

Policy is the authority boundary. Interfaces and providers are not.

All action paths must follow:

1. agent/tool/CLI request
2. provider registry validation
3. target registry validation
4. capability request
5. policy decision
6. operator approval if required
7. provider adapter
8. structured audit event
9. result

## Layers

### Interface Layer

MCP tools, CLI commands, API handlers, and agent workflows live here. Their job
is to describe intent, resolve configured providers and targets, and submit
capability requests to the control plane. They must not import or call provider
adapters directly.

The current MCP scaffold provides internal MCP-style models, a tool registry,
and a router that uses provider and target registries. It does not start a live
MCP server yet.

The current CLI adapter uses the same mock-only registry and control-plane path
as MCP.

### Provider Registry

The provider registry stores explicit provider entries. Unknown providers,
duplicate providers, disabled providers, and unsupported provider types fail
closed. The mock provider is the only default executable provider.

### Target Registry

The target registry stores explicit target entries. Unknown targets, disabled
targets, targets referencing unknown providers, and provider/target mismatches
fail closed.

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

The current implementation includes:

- capability registry and policy decision engine
- approval and audit models
- mock-only approval resumption model
- local JSONL audit persistence scaffold
- control-plane router for mock provider execution
- provider registry and target registry
- safe mock-only config loader
- safe stateful mock provider
- disabled real-provider placeholders
- MCP-style models, registry, and router
- mock-only CLI adapter
- CLI/MCP consistency matrix
- offline tests

Real provider implementations and live MCP SDK testing remain deferred.

## Design Rule

If a component can touch real infrastructure, it must be reachable only through
the control plane and only after policy and approval requirements have been
satisfied.
