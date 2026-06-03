# Control Plane

The AgenticKVM control plane is the mandatory path from agent intent to provider
execution.

## Request Lifecycle

1. Interface receives an agent or operator request.
2. Interface creates a capability request.
3. Capability registry resolves the capability family and risk.
4. Policy engine evaluates the request.
5. Approval broker asks the operator if required.
6. Provider adapter executes the authorized request.
7. Audit writer records structured events.
8. Result returns to the caller.

## Visible Modes

- Observe: read-only observation with redacted secrets.
- Assisted: conservative guided control with approval for material changes.
- Supervised: broader operation with dangerous actions gated.
- Full Control: in-scope allowed actions may skip prompts, but hard invariants
  still apply.
- Custom: explicit policy for a target class, session, or environment.

## Internal Decisions

- `deny`
- `ask_each_time`
- `ask_once_per_session`
- `allow`
- `allow_with_limits`

Unknown capability behavior is always `deny`.

## Capability Families

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

## Supervised Dangerous Gates

Supervised mode must gate:

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

Each gate must explain target, scope, reason, risk, approval duration, and audit
outcome.

## Full Control Limits

Full Control bypasses prompts only for in-scope allowed actions. It does not
bypass scope, limits, audit, emergency stop, secret redaction, or hard
invariants.
