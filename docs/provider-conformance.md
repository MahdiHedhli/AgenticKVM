# Provider Conformance

Provider conformance tests define the minimum safe behavior expected from every
provider adapter before any live transport exists.

## Scope

The conformance suite applies to:

- `MockProvider`
- fixture-backed PiKVM observe provider
- fixture-backed Redfish observe provider

It does not approve live provider access.

## Required Checks

- Provider id, type, enabled state, risk class, capabilities, and status are
  explicit and safe to display.
- Disabled providers fail closed.
- Unsupported and unknown capabilities fail closed.
- Observe-only providers expose only observe capabilities.
- Mutating capabilities do not execute on observe-only providers.
- Provider results are structured and report `performed_on_hardware=false` for
  mocks and fixtures.
- Secret-shaped parameter values are redacted or absent from provider output.
- Fake providers do not read environment secrets.
- Provider modules do not import live IO clients.
- Interface-level tests prove CLI and MCP do not call providers directly.

## Current Boundary

Conformance is an offline contract. It uses fake transports, fixtures, and local
provider objects only. Future live providers must pass this suite before manual
smoke testing can be considered.
