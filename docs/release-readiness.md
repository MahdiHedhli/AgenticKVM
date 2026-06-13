# Release Readiness

AgenticKVM release readiness is about preserving the safety contracts before
publishing a version or merging a release-quality branch. It does not imply live
provider readiness.

## Current Scope

The current mainline scope is:

- spec-driven control-plane baseline
- policy core
- approval and audit baseline
- mock provider baseline
- MCP scaffold and host compatibility layers
- provider, target, config, CLI, and docs readiness
- PiKVM observe-only readiness design
- local operator approval transport
- local operator console
- SQLite audit backend v1
- safe recovery playbook framework
- live-provider preflight gates
- static GitHub Pages site
- mock-only CI and release quality gates

The following remain deferred:

- M7 real provider slice
- live PiKVM transport
- live Redfish transport
- live MCP server adoption
- in-band remote desktop/session providers
- external production audit backend or SIEM integration

## Release Principles

Every release candidate must preserve these principles:

- policy remains the authority boundary
- unknown providers, targets, and capabilities fail closed
- real providers remain disabled by default
- tools and adapters do not call providers directly
- approval gates are first-class results
- audit cannot be silently disabled
- emergency stop cannot be disabled by the agent
- secrets and credential references are redacted
- CI remains mock-only
- public docs do not overclaim live provider support

## Required Local Checks

Run:

```bash
python scripts/check-package.py
python scripts/build-package.py
python scripts/smoke-cli.py
python scripts/lint-sanity.py
python scripts/type-sanity.py
python scripts/validate-docs.py
python scripts/check-site.py
uv run --offline --with pytest --python python3.13 python -m pytest
```

If offline testing cannot run because the local cache is missing, document the
safe fallback command and why it was used.

## Required CI Checks

The CI workflow should pass with:

- package metadata validation
- package artifact validation or documented deferred status
- CLI smoke matrix
- lint sanity
- type sanity
- docs/spec validation
- static site validation
- pytest

CI must not require secrets, provider credentials, live hardware, live provider
targets, remote desktop software, or a live MCP server.

## Required Documentation Checks

Before release:

- README status is accurate
- security model is current
- control-plane docs reflect the implementation
- provider contracts remain fail-closed
- provider taxonomy keeps AgenticKVM out-of-band only and points parked
  in-band/session scope to the parking lot
- roadmap reflects achieved, partial, and deferred work
- GitHub Pages site does not claim deferred live support
- release branch review package is complete

## Required Safety Checks

Before release, verify:

- unknown capability denied
- unknown provider denied
- unknown target denied
- disabled provider denied
- disabled target denied
- raw secret reveal denied
- policy modification denied
- audit disable denied
- emergency stop disable denied
- live provider placeholders disabled
- live PiKVM/Redfish configs rejected by default
- CLI/MCP/host paths preserve `ControlPlane`
- audit redaction remains intact
- artifact raw bytes are not leaked in audit

## Packaging Checks

Before release:

- package metadata imports cleanly
- CLI entry point metadata exists
- package name and version are intentional
- package metadata does not include the SDK trial dependency
- package build command is either verified or explicitly deferred
- release manifest generation writes only to an explicit safe path
- release artifacts do not include secrets or generated local audit/artifact
  outputs
- generated SQLite DBs, audit exports, checkpoints, approval queues, screenshots,
  and artifact files are not committed

## Public Beta Checks

Before public beta review:

- public beta readiness checklist is current
- public beta risk register is current
- SQLite audit hardening review is current
- live-provider preflight docs and tests are current
- approval queue and playbook safety docs are current
- live providers remain gated/deferred
- SDK trial dependency remains outside this branch

## GitHub Pages Checks

The Pages workflow may publish static `site/` files only. It must not:

- require secrets
- install runtime dependencies
- run provider tests
- run live smoke tests
- include analytics or tracking
- reference live infrastructure targets

Repository settings may still need GitHub Pages enabled for the branch to deploy.

## Human Review Gate

A human reviewer should confirm:

- branch diff is scoped to the release-quality lane
- SDK trial dependency did not enter the branch
- workflows are secret-free and mock-only
- public site claims match implementation status
- release checklist is complete
- rollback plan is clear

## Rollback

Rollback for this branch is straightforward:

1. Disable or remove the new workflow files if they cause CI or Pages issues.
2. Revert release-quality commits in reverse order.
3. Keep mainline free of trial-only MCP SDK dependency unless separately
   approved.
4. Re-run package, docs, and pytest checks after rollback.
