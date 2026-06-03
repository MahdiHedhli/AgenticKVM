# CLI

The `agentickvm` CLI is a safe adapter over the internal MCP-style router and
ControlPlane path. It is not an authority boundary and it does not call
providers directly.

## Current Commands

```text
agentickvm list-providers
agentickvm list-targets
agentickvm call --target mock-host --tool observe_screen
agentickvm call --target mock-host --tool get_power_state
```

The CLI emits JSON for tests and future automation.

## Safety

- Defaults to a built-in mock-only config.
- Does not read global user config by default.
- Does not read secrets from the environment.
- Requires explicit targets.
- Unknown targets fail closed.
- Unknown tools fail closed.
- Provider names supplied in a request must match the configured target.
- Dangerous actions return `approval_required` or `denied`; the CLI never
  auto-approves.

The CLI flow is:

1. CLI request
2. provider registry
3. target registry
4. MCP tool registry
5. capability request
6. ControlPlane policy/approval/audit
7. provider adapter only if allowed
8. structured JSON result

Real provider CLI usage remains deferred.

## Consistency

CLI and MCP status behavior is covered by `docs/interface-consistency.md` and
contract tests. Equivalent mock-target requests must return the same status for
the same mode and tool.
