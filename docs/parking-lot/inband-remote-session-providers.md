# Parking Lot: In-Band Remote Session Providers

Status: parked. This is not on the active AgenticKVM roadmap.

AgenticKVM is an out-of-band control-plane project. Its active provider scope is
KVM, BMC, PiKVM, Redfish, iLO, iDRAC, IPMI, Supermicro BMC, and the policy,
approval, audit, provider, and target registry machinery required to operate
those surfaces safely.

The former Spec 007 work for RustDesk, VNC, RDP, MeshCentral, BrowserBridge, and
desktop/session brokers has been moved out of the active specification set.
Those systems are in-band or session-level surfaces. They generally depend on a
running operating system, reachable network path, working remote access service
or agent, credentials, and sometimes active user/session state. They do not
provide the out-of-band trust or availability properties required for the core
AgenticKVM recovery mission.

## Why This Is Parked

- AgenticKVM must stay focused on out-of-band recovery and control.
- The public launch gate is a real wedged-machine recovery through the full
  approval chain, not a mock or in-band session demo.
- In-band remote desktop scope would dilute the threat model and provider
  semantics before the out-of-band approval broker and live observe slices are
  mature.
- Remote desktop streams, keyboard/mouse control, clipboard, file transfer,
  remote commands, and agent installation are high-risk behaviors that deserve a
  separate product decision.

## Possible Future Use

The parked work may become a separate future project that borrows the
AgenticKVM control plane. If that happens, it must define its own constitution,
provider contracts, approval model, artifact policy, consent model, and launch
criteria. It must not be marketed as out-of-band control.

## Non-Goals For AgenticKVM

AgenticKVM does not implement, roadmap, or ship:

- RustDesk providers
- VNC providers
- RDP providers
- MeshCentral providers
- BrowserBridge providers
- desktop/session broker providers
- remote desktop live behavior
- clipboard transfer
- file transfer
- remote command execution
- remote access agent install/update/control

## Historical Note

Earlier documentation treated these systems as future roadmap families. That is
superseded by the locked direction: AgenticKVM is out-of-band only.
