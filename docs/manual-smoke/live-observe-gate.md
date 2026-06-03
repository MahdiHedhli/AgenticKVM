# Live Observe Gate

This gate must pass before any future live observe smoke test.

## Required Approval

- Operator approved the exact provider, target, capability set, and time window.
- The approval is for observation only.
- The approval does not allow mutation, target expansion, audit disablement, or
  credential reuse outside the approved scope.

## Scope

- One provider.
- One target.
- Isolated lab infrastructure only.
- Observe-only capabilities.
- No power, reset, media, boot, BIOS, firmware, storage, network, account, BMC
  credential, input, runtime, or secret reveal actions.

## Config

- Live config is outside the repo.
- Provider is disabled before and after the smoke.
- Credentials use `credential_ref`.
- Raw credentials are not in config, argv, logs, shell history, docs, fixtures,
  or audit output.
- Artifact paths are explicit and outside tracked repo paths.
- Audit paths are explicit and outside tracked repo paths unless the operator
  has a separate archival plan.
- Fixture mode and live mode cannot both be enabled.

## Transport

- Timeout policy reviewed.
- TLS verification policy reviewed.
- Insecure TLS is not default and must be explicitly approved if used.
- Redfish is GET-only.
- PiKVM is observe-only and must use the provider-specific transport boundary.
- Redirects are either disabled or explicitly reviewed.
- Credential references are resolved only by an approved future backend, never
  by tests.
- Screenshot capture is approved separately if it is part of the smoke.

## Preflight

- List providers and targets before observe calls.
- Run mutating tool denial checks before observe calls.
- Confirm CLI/MCP paths route through registries and `ControlPlane`.
- Confirm audit sink is writable.
- Confirm artifact root is writable and outside the repo.
- Confirm CI is not running.
- Confirm no unrelated dirty worktree changes exist.

## Stop Conditions

Stop immediately on:

- unexpected write prompt
- auth error
- authorization error
- certificate error
- redirect
- timeout storm
- unknown response shape
- missing audit event
- raw secret exposure
- raw screenshot bytes in audit, CLI, MCP, logs, or committed files
- artifact output path inside the repository
- any mutating operation or action URI

## After The Smoke

- Verify the audit chain.
- Archive audit artifacts.
- Disable the provider.
- Remove local credential references if no longer needed.
- Remove local screenshot artifacts according to the smoke plan.
- Confirm no repo changes include secrets.
- Confirm no repo changes include screenshots or live endpoint details.
