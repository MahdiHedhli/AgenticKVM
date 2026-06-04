# Specification: In-Band Remote Session Providers

## Status

Roadmap-only. No RustDesk, VNC, RDP, MeshCentral, BrowserBridge, or remote
desktop live behavior is implemented by this spec.

## Summary

In-band remote session providers can complement out-of-band providers for
OS-level interactive workflows. They are not out-of-band providers because they
generally require a running operating system, network path, remote access
service or agent, credentials, and sometimes user/session state.

## Providers In Scope For Future Specs

- RustDesk
- VNC
- RDP
- MeshCentral

## Initial Future Slices

1. Provider inventory and specification only.
2. Session metadata observe-only.
3. Screenshot or stream metadata, if safe and redacted.
4. Input/control only after policy gates, approval behavior, audit, and
   consent/notification requirements are specified.
5. File transfer disabled by default.
6. Clipboard disabled by default.
7. Privileged/admin actions gated.
8. Credentials by reference only.
9. No unattended remote desktop control by default.

## Explicitly Disallowed In Early Slices

- file transfer
- clipboard write
- credential reveal
- unattended control of production desktops
- privilege escalation
- remote command execution
- installing agents
- modifying remote access settings
- bypassing user consent where applicable

## Required Control Flow

Every future in-band provider action must flow through provider registry,
target registry, capability request, policy, approval when required, provider
adapter, audit, and structured result.

No remote desktop adapter may call providers directly from CLI, MCP, SDK,
browser/session bridge, or agent workflow code.

## Acceptance Criteria Before Implementation

- Provider-specific spec exists.
- Capability mappings exist.
- Session metadata observe-only tests exist.
- Remote desktop stream and screenshot artifact policy is documented.
- Clipboard and file transfer risks are documented.
- Credential references are validated but not revealed.
- CI uses fake transports only.
- User consent/notification expectations are documented where applicable.
