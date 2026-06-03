# Control Plane

The AgenticKVM control plane is the mandatory path from agent intent to provider
execution.

## Request Lifecycle

1. Interface receives an agent or operator request.
2. Provider registry validates the configured provider.
3. Target registry validates the configured target and provider match.
4. Interface creates a capability request.
5. Capability registry resolves the capability family and risk.
6. Policy engine evaluates the request.
7. Approval broker asks the operator if required.
8. Provider adapter executes the authorized request.
9. Audit writer records structured events.
10. Result returns to the caller.

MCP requests follow the same lifecycle. The MCP router maps tool names to
capability ids, resolves the target/provider through registries, and calls
`ControlPlane`; it does not call providers directly.

CLI requests follow the same lifecycle through the MCP-style router.

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

Unknown MCP tool names and MCP mappings to unknown capabilities also fail
closed.

Unknown providers, unknown targets, disabled providers, disabled targets, and
provider/target mismatches also fail closed before provider execution.

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

MCP requests cannot use a requested mode field to self-escalate the active
policy.
