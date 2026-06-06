# Safe Recovery Playbooks

AgenticKVM playbooks are provider-neutral recovery workflows. They are built
from MCP tool calls and run through the existing target registry, provider
registry, policy engine, approval/audit flow, and `ControlPlane`.

Playbooks do not call providers directly.

## Commands

List playbooks:

```bash
agentickvm playbooks list
```

Dry-run a playbook:

```bash
agentickvm playbooks dry-run observe-target-health --target mock-host
```

Run a mock-safe playbook:

```bash
agentickvm playbooks run observe-target-health --target mock-host
```

Use an explicit audit path when persistence is needed:

```bash
agentickvm --audit-path /tmp/agentickvm-playbook-audit.jsonl \
  playbooks run observe-target-health --target mock-host
```

## Initial Playbooks

- `observe-target-health`
- `capture-screen-evidence`
- `inspect-boot-status`
- `collect-pre-recovery-evidence`
- `wait-for-login-prompt`

These first playbooks are observe-first and mock/fixture safe. They are meant
to collect pre-recovery evidence, not mutate a machine.

## Execution Rules

The runner:

- supports dry-run
- executes steps through `MCPRouter`
- uses registered targets and providers only
- relies on `ControlPlane` for policy decisions
- records normal audit events through the configured audit sink
- stops when a step returns `approval_required`, `denied`,
  `validation_error`, `provider_error`, or `policy_error`

## Disallowed For This Slice

- live provider execution by default
- provider bypass
- credential resolution
- raw secret reveal
- direct keyboard/mouse control against real machines
- power, media, boot, BIOS, firmware, storage, network, or BMC mutation
- unattended production recovery

## Future Work

Future recovery playbooks may add approval checkpoints, richer rollback notes,
operator prompts, and lab-only live smoke plans. Mutating playbooks must remain
policy-gated, approval-gated, audited, and disabled for real providers until an
operator explicitly approves a bounded manual smoke.
