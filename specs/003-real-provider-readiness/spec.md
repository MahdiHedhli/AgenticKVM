# Spec 003: Real Provider Readiness

## Status

Draft for readiness gates only. This spec does not approve or implement a live
PiKVM, Redfish, iLO, iDRAC, IPMI, Supermicro, Proxmox, or physical-host
provider.

## Goal

Define the mandatory gates before AgenticKVM may add the first observe-only real
provider slice.

## Scope

In scope:

- readiness gates for real provider work
- observe-only first-slice capability boundary
- provider registry, target registry, config, audit, redaction, and CI gates
- manual smoke-test prerequisites

Out of scope:

- live provider network calls
- credentials or secret loading
- mutating real-provider actions
- live MCP SDK integration
- CI against real hardware

## First Allowed Real-Provider Slice

The first real-provider implementation may only support observe capabilities:

- `observe.power_state`
- `observe.hardware_inventory`
- `observe.sensors`
- `observe.event_logs`
- `observe.boot_status`
- `observe.screen`, only when the provider supports it and screenshot handling
  is safe, redacted, and documented

## Explicitly Not Allowed

The first real-provider slice must not implement:

- `power.on`
- `power.force_off`
- `power.force_restart`
- `power.power_cycle`
- `media.mount_arbitrary_iso`
- `boot.change_boot_order`
- `bios.change_setting`
- `firmware.update_bios`
- `firmware.update_bmc`
- `storage.*`
- `network.*`
- BMC credential changes
- `secrets.*`

## Acceptance Criteria

- All readiness gates in `contracts/real-provider-gates.md` are satisfied.
- Real provider entries are disabled by default.
- CI remains mock-only.
- Manual smoke docs exist before first live use.
- Provider credentials are represented by secret references only and are never
  stored in repo config.
- Dangerous actions remain unimplemented or hard-denied.
