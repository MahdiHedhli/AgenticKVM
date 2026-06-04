# Research: In-Band Remote Session Providers

## Availability Assumptions

RustDesk, VNC, RDP, and MeshCentral generally require the operating system and
remote access service or agent to be running. They are useful when the OS is
reachable, but they do not replace PiKVM, Redfish, iLO, iDRAC, IPMI, or other
BMC/KVM out-of-band systems.

## Risk Notes

- Remote desktop streams can expose sensitive user data.
- Clipboard access can reveal or inject secrets.
- File transfer can exfiltrate data or introduce tools.
- Remote command execution can bypass intended workflows.
- Agent install/update can create persistence and fleet-management risk.
- User consent and notification may be legally or operationally required.

## Provider Notes

### RustDesk

Future RustDesk work should begin with metadata about configured sessions and
never assume unattended control is acceptable by default.

### VNC

Future VNC work should account for weak legacy security modes, password-only
deployments, and screen privacy risk.

### RDP

Future RDP work should account for domain identity, session ownership, drive
redirection, clipboard redirection, and administrative session risk.

### MeshCentral

Future MeshCentral work should account for agent lifecycle, remote command
features, file transfer, and fleet-management authority.
