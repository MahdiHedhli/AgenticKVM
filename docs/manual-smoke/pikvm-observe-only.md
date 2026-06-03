# PiKVM Observe-Only Manual Smoke

This guide is for a future operator-approved live smoke test. It must not run
in CI and must not be used until real-provider readiness gates are satisfied.

Current repository state: live PiKVM transport is not implemented. Do not run
this guide as an operational procedure yet. Use
`examples/config/pikvm-observe-fixture.yaml` for offline fixture tests only.

## Prerequisites

- Explicit operator approval for one isolated lab target.
- Live observe gate completed.
- One provider and one target only.
- Observe-only session scope.
- PiKVM provider disabled by default until the operator enables it locally.
- Config stored outside the repo.
- Credentials supplied through an approved `credential_ref`, never raw config.
- Audit output path explicitly configured.
- Screenshot/artifact output path explicitly configured outside the repo.
- Timeout and TLS verification behavior reviewed before the test.
- Mutating MCP/CLI tools verified unavailable before the smoke.

## Future Local Config Shape

This shape is for an operator-managed file outside the repository after live
transport support exists. It is not a committed example and it must not contain
raw secrets.

```json
{
  "version": "0.1",
  "providers": [
    {
      "id": "pikvm-lab-observe",
      "type": "pikvm",
      "enabled": true,
      "credential_ref": "keychain://agentickvm/lab/pikvm-observe",
      "metadata": {
        "live_mode": true,
        "fixture_mode": false,
        "base_url": "https://pikvm.lab.example.invalid",
        "connect_timeout_seconds": 2,
        "read_timeout_seconds": 5,
        "total_timeout_seconds": 10,
        "tls_verify": true,
        "allow_insecure_tls": false,
        "artifact_output_path": "/tmp/agentickvm-pikvm-artifacts",
        "audit_path": "/tmp/agentickvm-pikvm-audit.jsonl"
      }
    }
  ],
  "targets": [
    {
      "id": "pikvm-lab",
      "provider": "pikvm-lab-observe",
      "enabled": true,
      "environment": "isolated-lab",
      "labels": ["pikvm", "observe-only", "manual-smoke"],
      "risk_tier": "high",
      "allowed_modes": ["Observe"]
    }
  ],
  "default_policy": {
    "mode": "Observe"
  }
}
```

`base_url` above is documentation-safe. A real local file must use only the
approved isolated lab target and must remain outside the repo.

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

Preflight denial checks:

```text
agentickvm --config ./lab-pikvm-observe.yaml call --target pikvm-lab --tool power_on --mode Observe
agentickvm --config ./lab-pikvm-observe.yaml call --target pikvm-lab --tool type_text --mode Observe
agentickvm --config ./lab-pikvm-observe.yaml call --target pikvm-lab --tool mount_media --mode Observe
```

Each preflight denial check must return `denied` or another fail-closed status
without provider execution.

## Expected Safe Output

- `status` is `ok` only for read-only observations.
- Output must not contain raw credentials, tokens, cookies, or secret material.
- Screenshot or screen results should be treated as sensitive observations.
- Screenshot output must include metadata only unless artifact storage was
  explicitly approved and configured.
- Artifact names must not include target ids, provider ids, hostnames, or IPs.

## Audit Artifacts

Collect:

- capability request event
- policy decision event
- provider execution started and completed events
- final result event
- artifact metadata, if screenshot observation was approved

Audit artifacts must not be erased or hidden after the test.
Audit artifacts must not contain raw screenshot bytes.

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
- screenshot artifact path points into the repository
- screenshot artifact name includes the target id, provider id, hostname, or IP
- audit events are missing
- the target is not the approved isolated lab machine

## Rollback And Cleanup

- Disable the provider entry.
- Remove local secret references from the operator machine if no longer needed.
- Archive audit artifacts according to the local test plan.
- Remove local screenshot artifacts after review according to the local test
  plan.
- Do not commit local live config or credentials.
- Do not commit screenshot artifacts.
- Confirm no repo changes include secrets.
