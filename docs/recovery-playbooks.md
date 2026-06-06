# Recovery Playbook Safety

Recovery playbooks are automation scaffolds for repeatable, audited recovery
workflows. In the current branch they are mock/fixture safe and observe-first.

## Safety Requirements

Every playbook must:

- declare a name, description, risk tier, and rollback notes
- declare required capabilities
- use known MCP tools only
- route through `MCPRouter`
- route through `ControlPlane`
- stop on `approval_required`
- stop on denied, validation, policy, or provider errors
- emit normal control-plane audit events
- redact secret-like params in output

## Current Playbook Scope

Current playbooks collect evidence through observe capabilities. They do not
perform power, media, boot, BIOS, firmware, storage, network, credential, or
input-control actions.

## Future Mutating Playbooks

Future mutating playbooks require a separate spec update and must include:

- explicit capability mapping
- explicit risk tier
- rollback and cleanup notes
- approval checkpoints
- audit requirements
- mock/fake provider tests first
- live-provider preflight gates before any manual smoke

No playbook may bypass policy, approval, audit, provider registry, target
registry, or `ControlPlane`.
