# AgenticKVM Public Beta 0.1.0 Release Notes

Release tag: `v0.1.0-public-beta.1`

Package metadata at release time: `0.0.0`

Status: published pre-release after explicit maintainer approval.

## Summary

AgenticKVM public beta is a mock-first, safety-first control-plane release
candidate for agentic infrastructure operations. It demonstrates the authority
path that future live providers must follow:

agent/tool request -> registry resolution -> policy decision -> approval when
required -> provider adapter -> audit event -> structured result.

This beta is intended for code review, mock/fixture testing, documentation
review, and provider-readiness planning. It is not a production hardware
automation release.

GitHub Pages is enabled for GitHub Actions and publishes the static site at
`https://mahdihedhli.github.io/AgenticKVM/`. The release tag and GitHub
pre-release are intentionally published through an operator-controlled manual
cutover after final review, not by CI automation.

## What Works Today

- Constitution-backed control-plane rules.
- Capability registry and policy decisions with default-deny unknown
  capabilities.
- Provider and target registries.
- Safe mock provider.
- PiKVM and Redfish fake/fixture observe paths.
- CLI commands for provider/target listing and mock/fixture capability calls.
- Local operator approval queue with pending, approved, denied, expired, and
  consumed states.
- Local operator console via `agentickvm status` and `agentickvm console`.
- Local JSONL and SQLite audit paths with redaction and hash-chain
  verification.
- SQLite audit event listing, export, checkpoint, and inspect workflows.
- Safe recovery playbooks that run through `MCPRouter` and `ControlPlane`.
- Dependency-free MCP SDK adapter and host compatibility scaffolds.
- Static GitHub Pages site and release-quality workflows.
- Final public beta cutover, merge, tagging, Pages enablement, and maintainer
  review docs.
- Release validation scripts for package metadata, CLI smoke, lint sanity, type
  sanity, docs/specs, site safety, and release manifest generation.
- Live-provider preflight gates that block CI/test mode and require explicit
  operator evidence before any future live observe work.

## Safety Model

This beta keeps safety behavior visible and testable:

- policy is the authority boundary
- tools and workflows must not call providers directly
- unknown capabilities fail closed
- disabled providers and targets fail closed
- `approval_required` is a first-class result
- audit is mandatory
- secrets and credential refs are redacted
- CI is mock-only
- live providers are disabled by default

## Explicitly Not Implemented

- Live PiKVM network transport execution.
- Live Redfish network transport execution.
- PiKVM keyboard/mouse/input against hardware.
- Redfish POST/PATCH/DELETE or mutation actions.
- Live MCP server adoption.
- Python MCP SDK dependency on mainline.
- RustDesk, VNC, RDP, MeshCentral, BrowserBridge, or other live session
  providers.
- Production external audit backend, SIEM integration, or cloud storage backend.
- Production hardware recovery guarantees.

## Provider Readiness

PiKVM and Redfish are represented through specs, fake transports, fixture-backed
observe adapters, disabled placeholder configs, manual smoke docs, and
preflight gates. They are not live providers in this beta.

Future live-provider work must remain disabled by default, use credential
references only, preserve audit/approval behavior, and pass manual smoke gates
outside CI.

## MCP And SDK Status

AgenticKVM includes dependency-free MCP scaffolding and host compatibility
coverage. The Python MCP SDK trial remains on a separate branch:

- `trial/mock-only-mcp-python-sdk`

The trial dependency `mcp==1.27.2` is not adopted in this beta candidate.

## Known Limitations

- Package metadata still reports `0.0.0` until a maintainer approves a version
  bump.
- `scripts/build-package.py` reports `deferred` when the optional `build`
  module is unavailable.
- Full lint/type/coverage tooling remains documented but deferred.
- Public site is live through GitHub Pages. README badges remain deferred until
  the repository URL and release cadence are settled.
- SQLite audit backend v1 is local and explicit-path only.
- External production audit backend and SIEM integration are deferred.
- No live provider smoke has been run.

## Security Posture

Use this beta for mock-only evaluation and review. Do not use it for unattended
production hardware operations. Do not paste credentials, real hostnames, real
IP addresses, screenshots, audit databases, approval queue files, or generated
artifacts into issues or release assets.

Report vulnerabilities privately according to `SECURITY.md`.

## Validation

Expected local validation before release:

```bash
python3 scripts/check-package.py
python3 scripts/build-package.py
python3 scripts/smoke-cli.py
python3 scripts/lint-sanity.py
python3 scripts/type-sanity.py
python3 scripts/validate-docs.py
python3 scripts/check-site.py
python3 scripts/generate-release-manifest.py --output /tmp/agentickvm-public-beta-manifest.json
python3 scripts/check-public-beta.py
uv run --offline --with pytest --python python3.13 python -m pytest
```
