# Specification: Redfish Observe-Only Provider

## Status

Draft for provider-specific observe-only readiness. This spec does not approve
live Redfish execution and does not implement any Redfish POST, PATCH, DELETE,
reset, media, boot, BIOS, firmware, storage, network, account, or credential
mutation.

## Goal

Prepare AgenticKVM for a future Redfish provider slice that can observe BMC and
system state through the control plane while preserving policy, approval, audit,
and CI safety.

## Scope

In scope:

- Redfish observe-only capability mapping
- fake HTTP transport and fixture-backed tests
- disabled-by-default provider configuration examples
- GET-only future live boundary
- manual smoke prerequisites for future operator-approved live testing

Out of scope:

- live Redfish network calls
- credentials or secret loading
- `ComputerSystem.Reset`
- `Manager.Reset`
- virtual media insert/eject
- boot override
- BIOS settings changes
- firmware updates
- storage mutations
- network mutations
- account or user changes
- any POST, PATCH, DELETE, or other mutating request

## Allowed Future Observe Capabilities

The first live Redfish slice may support only:

- `observe.power_state`
- `observe.hardware_inventory`
- `observe.sensors`
- `observe.event_logs`
- `observe.boot_status`
- provider health/status

Each capability must route through provider registry, target registry,
capability request, policy decision, approval if required, provider adapter,
audit event, and structured result.

## Not Allowed

The first Redfish slice must not implement:

- reset actions
- `ComputerSystem.Reset`
- `Manager.Reset`
- virtual media insert/eject
- boot override
- BIOS settings changes
- firmware updates
- storage actions
- network changes
- account or user changes
- secrets
- any POST, PATCH, DELETE, or mutating action

## Safety Requirements

- Redfish providers are disabled by default.
- Future live transport must be GET-only for the first slice.
- Provider config must be explicit and target-scoped.
- Repo config must not contain credentials, tokens, passwords, cookies, or raw
  secrets.
- Tests must not read environment secrets.
- CI must use fake transports and fixtures only.
- Live smoke tests require explicit operator approval and isolated lab scope.
- Timeouts must be defined before live network transport exists.
- TLS verification and certificate validation behavior must be documented
  before live testing.
- Provider output must be redacted before interface results.
- Provider execution attempts must emit audit events.

## Acceptance Criteria

- Redfish provider-specific tests use fake transports only.
- The fake transport rejects POST, PATCH, DELETE, and other mutating methods.
- No test opens sockets, calls BMC endpoints, or reads credentials.
- Unsupported mutating capabilities are denied by policy or reported as
  provider-unsupported without touching hardware.
- Disabled Redfish placeholders cannot execute.
- Future live smoke docs exist before any live network implementation.
