# Live Provider Preflight

AgenticKVM live-provider preflight is a local validation gate for future
operator-approved PiKVM and Redfish observe-only work. It does not create a
provider transport, resolve credentials, contact hardware, or run live smoke.

The preflight gate exists so live-provider work cannot proceed until the
operator has explicitly provided the surrounding safety evidence.

## Scope

Current preflight scope is observe-only readiness for:

- PiKVM
- Redfish

The gate is not approval to run a live provider. It is a readiness check that
must pass before a separate manual smoke checklist is considered.

## Required Evidence

A live-provider preflight request must include:

- provider type and target ID
- explicit live-provider enablement outside committed defaults
- absolute external config path
- credential reference, without resolving it
- configured audit backend
- configured approval transport
- reviewed TLS policy
- reviewed timeout policy
- acknowledged manual smoke gate
- observe-only capability list
- artifact path for PiKVM screen or screenshot providers

The artifact path must be absolute and must not point inside the repository.

## Fail-Closed Rules

Preflight blocks when:

- CI mode is detected
- test mode is detected
- the provider type is unsupported
- live-provider enablement is missing
- the external config path is missing or relative
- `credential_ref` is missing
- audit backend evidence is missing
- approval transport evidence is missing
- PiKVM artifact path evidence is missing
- artifact path points into the repository
- TLS or timeout review is missing
- manual smoke acknowledgement is missing
- committed config enables a live provider
- any requested capability is outside observe-only/provider status scope

These blocks are intentional. Automated tests must never be able to green-light
live hardware access.

## CLI

The CLI exposes a dry local gate:

```bash
agentickvm \
  --config /path/to/external-live-config.json \
  --audit-sqlite-path /path/to/audit.sqlite \
  --approval-path /path/to/approvals.json \
  providers preflight \
  --target lab-target \
  --external-config /path/to/external-live-config.json \
  --artifact-path /path/to/operator-artifacts \
  --live-provider-enabled \
  --tls-reviewed \
  --timeout-reviewed \
  --manual-smoke-acknowledged
```

The command returns JSON and exits nonzero when blocked. During pytest or CI it
must return a blocked result.

The command validates config data only. It does not call `build_runtime`, does
not instantiate live adapters, does not open network sockets, and does not
resolve credential references.

## Manual Smoke Boundary

Passing preflight is not permission for unattended live smoke. Future live smoke
must still be:

- operator initiated
- observe-only for the relevant phase
- scoped to an external lab config
- backed by audit persistence
- backed by explicit approval transport
- documented with a rollback/stop checklist

PiKVM input, power actions, Redfish mutation, virtual media, BIOS, firmware,
storage, network, and account changes remain out of scope for this gate.
