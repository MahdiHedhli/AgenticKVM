# Plan: In-Band Remote Session Providers

## Phase 0: Roadmap And Boundary

- Document taxonomy and trust assumptions.
- Keep all providers roadmap-only.
- Do not add provider registry types until placeholder safety is reviewed.

## Phase 1: Metadata-Only Specs

- Define provider-specific metadata for RustDesk, VNC, RDP, and MeshCentral.
- Define session inventory fields that contain no secrets.
- Define audit and redaction behavior.

## Phase 2: Fake Transports

- Add fake transports or in-memory clients only.
- Add no live network calls.
- Add no credentials.
- Add no remote desktop control.

## Phase 3: Observe-Only Adapters

- Add disabled-by-default placeholder adapters only after registry and config
  risks are reviewed.
- Support session metadata observe-only first.
- Keep screenshots/streams metadata-only until artifact policy is proven.

## Deferred

- live remote desktop transport
- keyboard/mouse input
- clipboard
- file transfer
- remote command execution
- agent install/update
- unattended control
