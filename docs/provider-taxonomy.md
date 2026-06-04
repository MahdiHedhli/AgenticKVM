# Provider Taxonomy

AgenticKVM provider types have different availability and trust assumptions.
They must not be marketed or modeled as interchangeable.

## Categories

### Out-Of-Band Providers

Examples:

- PiKVM
- Redfish
- iLO
- iDRAC
- IPMI / Supermicro BMC

OOB providers can often observe or control a machine when the operating system
is down, reinstalling, unreachable, or stuck at BIOS or bootloader. They may
support pre-boot access and hardware-level recovery. They also carry high
availability and destructive-operation risk because power, boot, firmware,
virtual media, storage, and BMC/network settings may be exposed.

Recommended first slice: observe-only status, inventory, sensors, event logs,
boot status, or screen metadata with strict audit and redaction.

### In-Band Remote Session Providers

Examples:

- RustDesk
- VNC
- RDP
- MeshCentral

These are future in-band remote session providers. They generally require the
operating system, remote access service or agent, network path, credentials,
and sometimes user/session state to be working. They do not replace PiKVM,
Redfish, or BMC/KVM providers and must not be described as out-of-band
providers.

They complement OOB providers for OS-level interactive control after the OS and
remote desktop service are reachable.

Recommended first slice: provider inventory and session metadata observe-only.
Screenshot or stream metadata comes later. Input/control, file transfer,
clipboard, remote command execution, agent install/update, and unattended
control are high risk and must be gated separately.

### Browser/Session Providers

Examples:

- future BrowserBridge integration
- future local desktop/session brokers

Browser/session providers operate inside an existing browser, desktop, or
session broker context. They are useful for application-level or user-session
workflows, but they do not provide BMC/KVM recovery and may inherit the risks
of the active user session.

Recommended first slice: session inventory and safe observe metadata only.

## Trust And Availability Matrix

| Category | Works If OS Is Down | Pre-Boot/BIOS Access | Network Dependency | Credential Model | Typical Risk |
| --- | --- | --- | --- | --- | --- |
| Out-of-band | Often yes | Often yes | BMC/KVM network | Credential references, never raw secrets | Power, boot, firmware, media, storage, BMC changes |
| In-band remote session | Generally no | Generally no | OS plus remote desktop service | Credential references, user/session consent where applicable | Input/control, clipboard, file transfer, command execution |
| Browser/session | No | No | Active browser/session broker | Session-scoped references and user context | App/session manipulation and data exposure |

## Shared Requirements

All provider categories must follow the same AgenticKVM control model:

1. provider registry
2. target registry
3. capability request
4. policy decision
5. approval if required
6. provider adapter only if allowed
7. audit event
8. structured result

No provider category may bypass policy, approval, scope, audit, redaction, or
hard invariants.

If a provider category is exposed through a future MCP host, it must follow the
same host compatibility path:

```text
MCP host compatibility -> MCPSDKAdapter -> MCPRouter -> registries -> ControlPlane
```

The host layer is not a provider execution path. It must not call RustDesk,
VNC, RDP, MeshCentral, PiKVM, Redfish, or any other provider directly.

## In-Band Remote Session Risks

For RustDesk, VNC, RDP, and MeshCentral:

- remote desktop streams and screenshots are sensitive artifacts
- clipboard read/write is high risk
- file transfer is high risk
- remote command execution is high risk
- installing or modifying remote access agents is high risk
- unattended control of production desktops is high risk
- user notification or consent may be required depending on environment
- credentials must use references and must not be revealed to the model

Input/control, clipboard, file transfer, command execution, and unattended
remote desktop behavior must return `approval_required` or `denied` until
provider-specific specs, tests, and operator approval behavior are implemented.

Audit must record session metadata requests, denials, approvals, provider
attempts, and results. It must not record raw streams, clipboard contents, file
contents, credentials, or raw remote desktop secrets.

## Roadmap Status

RustDesk, VNC, RDP, MeshCentral, BrowserBridge, and desktop/session brokers are
roadmap-only. No implementation, live transport, credential resolution, remote
desktop control, file transfer, clipboard, remote command execution, or agent
installation exists in this repository.
