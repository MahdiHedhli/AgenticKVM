# AgenticKVM Constitution

## Purpose

AgenticKVM exists to provide safe agentic control for real machines through a
spec-driven control plane for out-of-band infrastructure operations.

This constitution is the highest authority in the repository. Specifications,
contracts, documentation, implementation, tests, and generated artifacts must
conform to it.

## Non-Negotiable Principles

### 1. Policy Is The Authority Boundary

Policy determines whether an action is denied, allowed, limited, or requires
operator approval. No lower layer may expand authority.

### 2. Unknown Capabilities Default To Deny

If a capability is absent from the registry, absent from policy, malformed, or
ambiguous, the decision is `deny`.

### 3. Tools Cannot Call Providers Directly

No MCP tool, CLI command, API handler, or agent workflow may call a provider
adapter directly. Every request must enter the control plane as a capability
request.

### 4. Provider Adapters Do Not Own Policy

Providers translate authorized requests into provider-specific behavior and
return structured results. They do not decide whether an action is safe,
approved, in scope, or allowed.

### 5. Full Control Bypasses Prompts, Not Scope, Audit, Or Invariants

Full Control may reduce approval prompts for in-scope allowed actions. It does
not bypass target scope, session scope, audit logging, emergency stop, secret
redaction, or hard invariants.

### 6. Agents Cannot Self-Escalate

Agents cannot change their own mode, policy, capability grants, approval
requirements, target scope, credentials, or provider access.

### 7. Secrets Are Never Revealed By Default

Secrets must be redacted by default in prompts, logs, audit events, traces, test
fixtures, and tool outputs. Raw reveal requires explicit scope, explicit
capability, explainable approval, and audit.

### 8. Audit Is Mandatory

Every capability request and result must produce structured audit events.
Denied, approved, expired, failed, limited, and executed actions are all
auditable.

### 9. Real Hardware Is Never Used In CI

Continuous integration must use mock providers, offline contracts, schemas, and
fixtures only. Real BMCs, KVMs, power controllers, and machines are opt-in local
or lab-only targets outside default CI.

### 10. Destructive Actions Require Explicit Scope

Actions that can destroy data, change boot behavior, alter firmware, disrupt
availability, reveal secrets, alter credentials, or affect external systems
require explicit target and session scope.

### 11. Operator Approval Must Be Explainable

Approval requests must clearly state what action is requested, why it is
requested, what target is affected, what risks exist, what policy caused the
prompt, and what will be audited.

### 12. Small Verified Slices Beat Broad Unsafe Automation

AgenticKVM should grow through narrow, tested, reversible increments. Broad
automation without clear policy, mocks, contracts, audit, and rollback thinking
is not acceptable.

## Required Control Flow

Every action must flow through:

1. agent/tool request
2. capability request
3. policy decision
4. operator approval if required
5. provider adapter
6. structured audit event
7. result

Any design that skips this flow is unconstitutional.

## Visible Control Modes

- Observe: read-only observation with secrets redacted and no state-changing
  provider actions.
- Assisted: low-risk actions may be allowed, while meaningful state changes ask
  the operator.
- Supervised: broader operations are available, but dangerous actions remain
  gated and explainable.
- Full Control: in-scope operations may run without prompts, but scope, audit,
  emergency stop, secret rules, and invariants still apply.
- Custom: explicit policy authored for a specific environment, target class, or
  session.

## Internal Policy Decisions

- `deny`
- `ask_each_time`
- `ask_once_per_session`
- `allow`
- `allow_with_limits`

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

## Dangerous Actions

The following actions are dangerous and must be documented and gated in
Supervised mode:

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

## Specification Discipline

Before implementation:

1. Define or update the relevant spec.
2. Define capability and policy contracts.
3. Define audit fields and approval behavior.
4. Add mock behavior and tests.
5. Implement the smallest safe slice.

## Amendment Process

Constitution changes require:

1. a clear rationale
2. explicit migration impact
3. security review
4. updates to affected specs, docs, contracts, and tests
5. a changelog entry

No amendment may silently weaken safety gates.
