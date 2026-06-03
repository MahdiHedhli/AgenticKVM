# Manual Smoke

Manual smoke docs are future operator checklists. They are not CI instructions
and they do not approve live provider execution.

## Rules

- Explicit operator approval is required.
- Use one isolated lab target.
- Use one provider and one target per smoke.
- Use observe-only scope.
- Keep live config outside the repo.
- Reference credentials; do not store them.
- Configure an audit path.
- Review timeout and TLS policy.
- Do not run in CI.
- Do not run mutating tools.
- Verify the audit chain afterward.
- Confirm no repo changes include secrets.

Provider-specific guides:

- [PiKVM Observe-Only](pikvm-observe-only.md)
- [Redfish Observe-Only](redfish-observe-only.md)
- [Live Observe Gate](live-observe-gate.md)
