# Live Provider And Input-Control Gates

This integration branch keeps live provider and PiKVM input-control work gated.
The current source-of-truth PiKVM spec remains observe-only and explicitly
disallows keyboard, mouse, paste, power, reset, media, boot, storage, network,
and BMC account changes.

## PiKVM Observe-Only Gate

Allowed future live PiKVM observe capabilities remain:

- provider health/status
- `observe.screen`
- `observe.screenshot` only when artifact policy allows it
- `observe.power_state` only through a safe read endpoint
- `observe.boot_status` only when inferable without mutation

Before live PiKVM code is accepted:

- transport code must be disabled by default
- config must require explicit external live mode
- credentials must remain references only
- tests must use fake transports only
- CI must not run live smoke
- manual smoke docs must be reviewed by an operator
- audit path and artifact path must be explicit
- no keyboard, mouse, paste, power, reset, media, boot, storage, network, or
  account mutation can be present in the live observe slice

## Redfish Observe-Only Gate

Allowed future live Redfish behavior remains GET-only:

- service root
- systems collection
- power state
- hardware inventory summary
- sensors
- event logs
- manager/system status

Before live Redfish code is accepted:

- POST, PATCH, DELETE, reset, boot override, virtual media, BIOS, firmware,
  storage, network, and account changes must be impossible in the first slice
- transport code must be disabled by default
- tests must use fake transports only
- CI must not run live smoke
- credential refs must not be resolved in tests
- manual smoke must be explicit and operator approved

## PiKVM Input-Control Gate

PiKVM input control is not implemented on this branch.

A future gated fake-only phase may introduce provider-neutral capability
coverage for:

- `input.keyboard_type`
- `input.mouse_click`
- `input.keyboard_key`
- `input.keyboard_shortcut`

That phase must start with mock/fake transport only and prove:

- input routes through `MCPRouter` and `ControlPlane`
- no live PiKVM input method exists by default
- raw secret typing is denied unless a future credential injection flow exists
- risky hotkeys require approval
- screenshot-before/after metadata is artifact-safe and fake-only
- audit events are emitted for every input step
- manual smoke docs say not to run live input unattended

The live input phase is explicitly disallowed until a later operator-approved
lab plan is reviewed.
