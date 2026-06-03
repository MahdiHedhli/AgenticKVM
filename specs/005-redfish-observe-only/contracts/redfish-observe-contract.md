# Contract: Redfish Observe-Only

## Required Behavior

- Accept only registered targets.
- Execute only after `ControlPlane` policy evaluation.
- Support only observe capabilities in the first slice.
- Use fake GET-only transport or fixtures in tests.
- Redact provider output before interface results.
- Emit audit events for provider execution attempts and results.

## Supported Fake Capabilities

- `observe.power_state`
- `observe.hardware_inventory`
- `observe.sensors`
- `observe.event_logs`
- `observe.boot_status`
- `observe.status`

## Forbidden Methods

The observe-only Redfish client must not expose live reset, virtual media, boot
override, BIOS, firmware, storage mutation, network mutation, account mutation,
credential mutation, or secret methods.

## Failure Rules

- Unknown capability: deny through policy.
- Unsupported capability: provider returns unsupported without hardware action.
- Disabled provider: fail closed.
- Missing fake transport: fail closed.
- Credentials in config: reject before runtime.
- Non-GET fake transport request: reject.
