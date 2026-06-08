# Public Beta Known Limitations

This document describes the limits of the AgenticKVM public beta candidate. It
is intentionally conservative so public users do not mistake roadmap or
readiness work for implemented live-provider support.

## Live Providers

- No live provider is enabled by default.
- Live PiKVM network transport execution is deferred.
- Live Redfish network transport execution is deferred.
- PiKVM input control against hardware is deferred.
- Redfish mutation actions are not implemented.
- RustDesk, VNC, RDP, MeshCentral, BrowserBridge, and desktop/session providers
  remain roadmap-only.

## MCP Server And SDK

- The dependency-free MCP adapter and host compatibility layers exist.
- A Python MCP SDK trial exists only on `trial/mock-only-mcp-python-sdk`.
- The trial dependency `mcp==1.27.2` is not part of this branch or mainline
  metadata.
- Live MCP server behavior is not adopted or enabled by default.

## Audit Backend

- SQLite audit backend v1 is local and explicit-path only.
- External production audit backend, SIEM export, cloud object storage, database
  service integration, and checkpoint signing are deferred.
- Audit exports and manifests must be generated to `/tmp` or ignored artifact
  paths, not committed.

## Packaging And Quality Gates

- Package metadata currently reports `0.0.0` until a maintainer approves a
  version bump.
- Wheel/sdist build verification reports `deferred` unless the optional
  `build` module is available.
- Full lint tooling, full type checking, and coverage percentage enforcement are
  documented but not yet mandatory release gates.

## GitHub Pages

- The static site and Pages workflow are present.
- GitHub Pages is enabled for GitHub Actions.
- Public site URL: `https://mahdihedhli.github.io/AgenticKVM/`
- README badges remain deferred until release cadence and badge policy are
  settled.

## Production Use

This beta candidate is not for unattended production hardware recovery. It is
appropriate for:

- reading specs and docs
- running mock-only tests
- reviewing policy/approval/audit architecture
- testing fake/fixture provider paths
- reviewing release-quality gates
- planning future live-provider work

Do not use this beta for:

- live hardware operations
- unattended recovery against production machines
- live PiKVM keyboard/mouse/input
- live Redfish reset, boot, firmware, BIOS, storage, network, or account
  changes
- storing secrets or raw credentials in config, issues, logs, audit exports, or
  release artifacts
