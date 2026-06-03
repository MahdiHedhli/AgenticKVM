# PiKVM Observe-Only Manual Smoke

This guide is for a future operator-approved live smoke test. It must not run
in CI and must not be used until real-provider readiness gates are satisfied.

## Prerequisites

- Explicit operator approval for one isolated lab target.
- Live observe gate completed.
- One provider and one target only.
- Observe-only session scope.
- PiKVM provider disabled by default until the operator enables it locally.
- Config stored outside the repo.
- Credentials supplied through an approved `credential_ref`, never raw config.
- Audit output path explicitly configured.
- Timeout and TLS verification behavior reviewed before the test.

## Scope

Allowed future checks:

- provider health/status
- `observe.screenshot` or `observe.screen`, if screenshot handling is approved
- `observe.power_state`
- `observe.boot_status`
- non-secret inventory or event observations when supported

Do not run:

- keyboard input
- mouse input
- paste
- power or reset actions
- virtual media actions
- boot changes
- storage, network, or BMC credential changes
- secret reveal

## Future Commands

These commands are examples for once a live PiKVM adapter exists. They are not
expected to work in the current scaffold.

```text
agentickvm --config ./lab-pikvm-observe.yaml list-providers
agentickvm --config ./lab-pikvm-observe.yaml list-targets
agentickvm --config ./lab-pikvm-observe.yaml call --target pikvm-lab --tool get_status --mode Observe
agentickvm --config ./lab-pikvm-observe.yaml call --target pikvm-lab --tool observe_screen --mode Observe
agentickvm --config ./lab-pikvm-observe.yaml call --target pikvm-lab --tool get_power_state --mode Observe
```

## Expected Safe Output

- `status` is `ok` only for read-only observations.
- Output must not contain raw credentials, tokens, cookies, or secret material.
- Screenshot or screen results should be treated as sensitive observations.

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
- a command would send keyboard or mouse input
- a command would power, reset, mount media, or change boot behavior
- a certificate warning is unexpected
- a redirect appears unexpectedly
- a timeout repeats
- the response shape is unknown
- output contains raw secret material
- audit events are missing
- the target is not the approved isolated lab machine

## Rollback And Cleanup

- Disable the provider entry.
- Remove local secret references from the operator machine if no longer needed.
- Archive audit artifacts according to the local test plan.
- Do not commit local live config or credentials.
- Confirm no repo changes include secrets.
