# Contract: PiKVM Observe-Only

## Required Behavior

- Accept only registered targets.
- Execute only after `ControlPlane` policy evaluation.
- Support only observe capabilities in the first slice.
- Use fake transport or fixtures in tests.
- Redact provider output before interface results.
- Emit audit events for provider execution attempts and results.

## Supported Fake Capabilities

- `observe.screenshot`
- `observe.power_state`
- `observe.boot_status`
- `observe.status`

Additional observations may be added only when they remain read-only and
fixture-backed.

## Forbidden Methods

The observe-only PiKVM client must not expose live keyboard, mouse, paste,
power, media, boot, storage, network, BMC credential, or secret mutation
methods.

## Failure Rules

- Unknown capability: deny through policy.
- Unsupported capability: provider returns unsupported without hardware action.
- Disabled provider: fail closed.
- Missing fake transport: fail closed.
- Credentials in config: reject before runtime.
