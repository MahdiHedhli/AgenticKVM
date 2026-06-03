# Provider Readiness Checklist

Use this checklist for each future real provider.

## Configuration

- [ ] Provider disabled by default.
- [ ] No endpoint in public examples.
- [ ] No secrets in repo config.
- [ ] Secret references documented separately from config.
- [ ] Provider type cannot be dynamically imported from config.

## Capabilities

- [ ] Capabilities map to `specs/002-control-plane` capability ids.
- [ ] Observe-only capabilities are separated from mutating capabilities.
- [ ] Unsupported capabilities fail closed.
- [ ] Dangerous capabilities are unimplemented or hard-denied.

## Safety

- [ ] CI uses mocks only.
- [ ] Manual smoke docs exist.
- [ ] Timeouts are defined.
- [ ] Error behavior is defined.
- [ ] Redaction behavior is defined.
- [ ] Audit events are defined for attempted execution.
- [ ] First live smoke requires human approval.

## Tests

- [ ] Mock provider contract tests pass.
- [ ] Placeholder provider disabled tests pass.
- [ ] Provider config secret rejection tests pass.
- [ ] No network calls occur in tests.
