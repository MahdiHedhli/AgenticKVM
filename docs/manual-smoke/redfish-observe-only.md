# Redfish Observe-Only Manual Smoke

This guide is for a future operator-approved live smoke test. It must not run
in CI and must not be used until real-provider readiness gates are satisfied.

## Prerequisites

- Explicit operator approval for one isolated lab BMC.
- Live observe gate completed.
- One provider and one target only.
- Observe-only session scope.
- Redfish provider disabled by default until the operator enables it locally.
- Config stored outside the repo.
- Credentials supplied through an approved `credential_ref`, never raw config.
- Audit output path explicitly configured.
- Timeout and TLS verification behavior reviewed before the test.
- First live slice restricted to GET-only Redfish operations.

## Scope

Allowed future checks:

- provider health/status
- `observe.power_state`
- `observe.hardware_inventory`
- `observe.sensors`
- `observe.event_logs`
- `observe.boot_status`

Do not run:

- `ComputerSystem.Reset`
- `Manager.Reset`
- virtual media insert/eject
- boot override
- BIOS settings changes
- firmware updates
- storage actions
- network changes
- account or user changes
- secret reveal
- any POST, PATCH, DELETE, or mutating Redfish action

## Future Commands

These commands are examples for once a live Redfish adapter exists. They are not
expected to work in the current scaffold.

```text
agentickvm --config ./lab-redfish-observe.yaml list-providers
agentickvm --config ./lab-redfish-observe.yaml list-targets
agentickvm --config ./lab-redfish-observe.yaml call --target redfish-lab --tool get_status --mode Observe
agentickvm --config ./lab-redfish-observe.yaml call --target redfish-lab --tool get_power_state --mode Observe
agentickvm --config ./lab-redfish-observe.yaml call --target redfish-lab --tool get_sensors --mode Observe
agentickvm --config ./lab-redfish-observe.yaml call --target redfish-lab --tool get_event_logs --mode Observe
```

## Expected Safe Output

- `status` is `ok` only for read-only observations.
- Output must not contain raw credentials, tokens, cookies, or secret material.
- Event logs should be redacted where provider output includes sensitive
  fields.

## Audit Artifacts

Collect:

- capability request event
- policy decision event
- provider execution started and completed events
- final result event

Audit artifacts must not be erased or hidden after the test.

## Stop Conditions

Stop immediately if:

- there is any unexpected write prompt
- there is an auth error or authorization error
- a request would use POST, PATCH, DELETE, or action URIs
- a request would reset, boot, mount media, update firmware, or modify BMC state
- a certificate warning is unexpected
- a redirect appears unexpectedly
- a timeout repeats
- the response shape is unknown
- output contains raw secret material
- audit events are missing
- the target is not the approved isolated lab BMC

## Rollback And Cleanup

- Disable the provider entry.
- Remove local secret references from the operator machine if no longer needed.
- Archive audit artifacts according to the local test plan.
- Do not commit local live config or credentials.
- Confirm no repo changes include secrets.
