# Real Provider Gates

These gates must pass before any observe-only real provider implementation can
be merged.

1. Mock provider contract tests pass.
2. Provider registry prevents arbitrary providers.
3. Target registry prevents unknown targets.
4. Config loader rejects secrets.
5. Real provider is disabled by default.
6. Real provider cannot run in CI.
7. Manual smoke docs exist before live testing.
8. Provider credentials are never stored in repo config.
9. Provider actions are capability-mapped.
10. Observe-only actions are separated from mutating actions.
11. Network calls are behind explicit operator config.
12. Timeouts and error handling are defined.
13. Audit events are emitted for attempted provider execution.
14. Redaction behavior is defined.
15. Dangerous actions remain unimplemented or hard-denied.
16. CI uses mocks only.
17. Human approval is required before first live smoke.

## First Slice Boundary

Allowed future observe-only capabilities:

- `observe.power_state`
- `observe.hardware_inventory`
- `observe.sensors`
- `observe.event_logs`
- `observe.boot_status`
- `observe.screen`, only if screenshots are safe and documented

Forbidden in the first slice:

- power mutation
- media mutation
- boot mutation
- BIOS mutation
- firmware mutation
- storage mutation
- network mutation
- BMC credential mutation
- raw secret access
