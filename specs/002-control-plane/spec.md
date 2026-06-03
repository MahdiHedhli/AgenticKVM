# Specification: Control Plane

## Summary

The AgenticKVM control plane is the only path from agent intent to provider
execution. It receives tool or workflow requests, converts them into capability
requests, evaluates policy, asks the operator when required, executes through a
provider adapter, emits structured audit events, and returns a result.

## Required Flow

1. Agent/tool request enters MCP, CLI, API, or workflow boundary.
2. Boundary layer creates a capability request.
3. Control plane resolves the capability registry entry.
4. Policy engine evaluates mode, target scope, session scope, limits, dangerous
   action flags, and invariants.
5. Approval broker asks the operator when the decision requires approval.
6. Provider adapter executes only authorized requests.
7. Audit writer records request, policy decision, approval state, provider
   result, and material risk.
8. Control plane returns a structured result to the caller.

No caller may bypass these steps.

## Capability Request

A capability request must include:

- capability id
- capability family
- action name
- target id or target selector
- session id
- requester identity
- parameters with secret references redacted
- intended effect
- correlation id

## Required Capability Families

- `session`
- `observe`
- `input`
- `power`
- `media`
- `boot`
- `bios`
- `firmware`
- `storage`
- `network`
- `bmc`
- `secrets`
- `runtime`

## Policy Decisions

- `deny`: request is not allowed.
- `ask_each_time`: request needs operator approval every time.
- `ask_once_per_session`: request needs approval once for the active session and
  matching scope.
- `allow`: request may execute without an approval prompt.
- `allow_with_limits`: request may execute only inside explicit constraints such
  as rate, count, duration, target set, or parameter allowlist.

Unknown capabilities, missing policy entries, malformed scope, and ambiguous
provider mappings evaluate to `deny`.

## Visible Control Modes

### Observe

Read-only observation. State-changing provider actions deny. Secrets are
redacted. Dangerous actions deny.

### Assisted

Low-risk, reversible actions may be allowed. Material state changes require
operator approval. Dangerous actions default to deny unless a custom policy
explicitly asks.

### Supervised

Broader action set for active operator-supervised work. Dangerous actions remain
gated with explainable approval and explicit scope.

### Full Control

In-scope allowed actions may bypass prompts. Full Control does not bypass
session scope, target scope, audit, emergency stop, secret redaction, limits, or
hard invariants.

### Custom

Explicit policy authored for a target class, session, or environment. Custom
policies must still satisfy the constitution and hard invariants.

## Dangerous Actions

The following are dangerous and must be gated in Supervised mode:

- force power actions
- NMI
- BMC reset
- arbitrary ISO mount
- boot override
- BIOS changes
- firmware updates
- network/BMC IP changes
- BMC credential changes
- disk format/wipe/repartition
- backup restore
- encryption changes
- raw secret reveal
- untrusted script/playbook execution
- external webhook calls
- subagent spawning

## Hard Invariants

These apply even in Full Control:

1. Agent cannot change its own policy.
2. Agent cannot disable audit logging.
3. Agent cannot disable emergency stop.
4. Agent cannot silently expand target scope.
5. Agent cannot silently add credentials.
6. Agent cannot reveal raw secrets by default.
7. Agent cannot persist new background services without logging them.
8. Agent cannot move to another target unless it is inside session scope.
9. Agent cannot erase audit artifacts.
10. Agent cannot hide material risk from the operator.
11. Agent cannot run destructive OOB actions against real hardware unless target
    and session scope explicitly allow it.
12. Agent cannot treat provider-specific reset, boot, firmware, or storage
    actions as generic low-risk actions.

## Provider Boundary

Provider adapters receive only authorized requests. A provider adapter must:

- identify itself and supported capability ids
- translate provider-neutral actions into provider-specific calls
- return structured results
- never decide policy
- never reveal raw secrets by default
- never erase audit artifacts
- never access targets outside request scope

## Audit Requirements

Every request must generate audit records for:

- request received
- capability resolved or denied as unknown
- policy decision
- approval requested, granted, denied, expired, or reused
- provider execution start and result when execution occurs
- final result returned to caller

Audit events must be structured and must redact secrets by default.

## Acceptance Criteria

- Unknown capability requests deny.
- Provider adapters cannot be reached directly from public tools.
- Supervised mode gates dangerous actions.
- Full Control cannot bypass hard invariants.
- All provider executions produce structured audit events.
- CI remains mock-only.
