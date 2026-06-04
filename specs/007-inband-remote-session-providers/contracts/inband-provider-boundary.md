# In-Band Provider Boundary Contract

## Boundary

In-band remote session providers are not out-of-band providers. They depend on
the operating system and remote access surface being available.

Future in-band providers must enter through:

1. provider registry
2. target registry
3. capability request
4. policy decision
5. approval if required
6. provider adapter only if allowed
7. audit event
8. structured result

## Early Slice Allowlist

Early slices may include:

- provider inventory
- target/session metadata
- connection status metadata
- non-secret version metadata
- screenshot or stream metadata only after artifact policy is approved

## Early Slice Denylist

Early slices must not include:

- file transfer
- clipboard write
- clipboard read unless explicitly scoped and approved
- credential reveal
- unattended production desktop control
- privilege escalation
- remote command execution
- agent installation
- agent update
- remote access settings changes
- bypassing user consent where applicable

## Credential Rule

Credentials must use references only. Raw credentials must not appear in config,
tests, logs, audit, CLI output, MCP output, SDK output, or provider results.

## Audit Rule

Audit must record session metadata requests, approvals, denials, provider
attempts, and results. Remote desktop screenshots, streams, clipboard data, and
file metadata are sensitive.

## CI Rule

CI must use fake transports and fixtures only. CI must not contact RustDesk,
VNC, RDP, MeshCentral, desktop brokers, or remote hosts.
