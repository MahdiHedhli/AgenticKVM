# Specification: PiKVM Observe-Only Provider

## Status

Draft for provider-specific observe-only readiness. This spec does not approve
live PiKVM execution and does not implement keyboard, mouse, power, media, boot,
or configuration changes.

## Goal

Prepare AgenticKVM for a future PiKVM provider slice that can observe a
configured target through the control plane while preserving the constitution:
policy is the authority boundary, audit is mandatory, and real hardware is
never used in CI.

## Scope

In scope:

- PiKVM observe-only capability mapping
- fake transport and fixture-backed tests
- disabled-by-default provider configuration examples
- screenshot and screen-content sensitivity rules
- manual smoke prerequisites for future operator-approved live testing

Out of scope:

- live PiKVM network calls
- credentials or secret loading
- keyboard input
- mouse input
- paste or text entry
- power actions
- virtual media actions
- boot changes
- storage, network, or BMC credential changes

## Allowed Future Observe Capabilities

The first live PiKVM slice may support only these capabilities, when the
provider can expose them safely:

- `observe.screen`
- `observe.screenshot`
- `observe.power_state`
- `observe.hardware_inventory`
- `observe.event_logs`
- `observe.boot_status`

Each capability must route through provider registry, target registry,
capability request, policy decision, approval if required, provider adapter,
audit event, and structured result.

## Not Allowed

The first PiKVM slice must not implement:

- keyboard input
- mouse input
- paste
- power actions
- reset actions
- virtual media
- boot changes
- storage changes
- network changes
- BMC credential changes
- secrets
- any write or mutating action

Any future method name for a mutating PiKVM action must hard-fail or remain
absent until a separate spec defines policy, approval, audit, and tests.

## Safety Requirements

- PiKVM providers are disabled by default.
- Provider config must be explicit and target-scoped.
- Repo config must not contain credentials, tokens, passwords, cookies, or raw
  secrets.
- Tests must not read environment secrets.
- CI must use fake transports and fixtures only.
- Live smoke tests require explicit operator approval and isolated lab scope.
- Timeouts must be defined before live network transport exists.
- TLS verification and certificate validation behavior must be documented
  before live testing.
- Screenshots and screen text are potentially sensitive and must be redacted or
  handled as audit-sensitive observations.
- Provider output must be redacted before interface results.
- Provider execution attempts must emit audit events.

## Acceptance Criteria

- PiKVM provider-specific tests use fake transports only.
- No test opens sockets, calls PiKVM endpoints, or reads credentials.
- Unsupported mutating capabilities are denied by policy or reported as
  provider-unsupported without touching hardware.
- Disabled PiKVM placeholders cannot execute.
- Future live smoke docs exist before any live network implementation.
