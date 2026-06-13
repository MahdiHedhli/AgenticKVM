# Provider Taxonomy

AgenticKVM is out-of-band only.

The active provider taxonomy is intentionally narrow. AgenticKVM focuses on
surfaces that can observe or recover machines outside the normal operating
system path: KVM, BMC, PiKVM, Redfish, iLO, iDRAC, IPMI, and Supermicro BMC.

## Active Provider Family

### Out-Of-Band Providers

Examples:

- PiKVM
- Redfish
- iLO
- iDRAC
- IPMI / Supermicro BMC

Out-of-band providers can often observe or control a machine when the operating
system is down, reinstalling, unreachable, wedged, or stuck at BIOS or a
bootloader. They may support pre-boot access and hardware-level recovery. They
also carry high availability and destructive-operation risk because power,
boot, firmware, virtual media, storage, and BMC/network settings may be exposed.

Recommended first live slice: observe-only status, inventory, sensors, event
logs, boot status, or screen metadata with strict policy, signed approval
grants, audit, redaction, and manual smoke gates.

## Shared Requirements

All active providers must follow the same AgenticKVM control model:

1. provider registry
2. target registry
3. capability request
4. policy decision
5. signed broker grant if approval is required
6. provider adapter only if allowed
7. audit event
8. structured result

No provider may bypass policy, approval, scope, audit, redaction, or hard
invariants.

If a provider is exposed through a future MCP host, it must follow the same
host compatibility path:

```text
MCP host compatibility -> MCPSDKAdapter -> MCPRouter -> registries -> ControlPlane
```

The host layer is not a provider execution path. It must not call PiKVM,
Redfish, iLO, iDRAC, IPMI, Supermicro BMC, or any other provider directly.

## Parked In-Band Scope

RustDesk, VNC, RDP, MeshCentral, BrowserBridge, desktop/session brokers, and
remote desktop/session providers are not on the AgenticKVM roadmap. They are
documented only in the parking lot:

- [Parking Lot: In-Band Remote Session Providers](parking-lot/inband-remote-session-providers.md)

They may become a separate future project that borrows the AgenticKVM control
plane, but AgenticKVM itself remains out-of-band only.
