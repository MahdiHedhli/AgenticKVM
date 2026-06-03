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

## Transport

- Timeout policy reviewed.
- TLS verification policy reviewed.
- Insecure TLS is not default and must be explicitly approved if used.
- Redfish is GET-only.
- PiKVM is observe-only.
- Redirects are either disabled or explicitly reviewed.

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
- any mutating operation or action URI

## After The Smoke

- Verify the audit chain.
- Archive audit artifacts.
- Disable the provider.
- Remove local credential references if no longer needed.
- Confirm no repo changes include secrets.
