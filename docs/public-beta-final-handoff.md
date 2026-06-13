# Public Beta Final Handoff

This handoff summarizes the public beta merge-readiness state for AgenticKVM.
It does not authorize a merge, tag, release publication, Pages settings change,
live provider smoke, or hardware operation.

## Project Status

- candidate branch: `feature/public-beta-cutover`
- candidate lineage: stacked from `main` through the release-quality,
  next-10-integration, audit-beta-readiness, and public-beta-cutover branches
- beta scope: mock-first public beta candidate for review and local fixture
  validation
- live providers: disabled and deferred
- live MCP server: deferred
- Python MCP SDK trial: separate on `trial/mock-only-mcp-python-sdk`
- proposed pre-release tag: `v0.1.0-public-beta.1`
- package metadata version: `0.0.0` until maintainer approval

## Final Validation Result

The following matrix passed during final review:

```bash
python3 scripts/check-package.py
python3 scripts/build-package.py
python3 scripts/smoke-cli.py
python3 scripts/lint-sanity.py
python3 scripts/type-sanity.py
python3 scripts/validate-docs.py
python3 scripts/check-site.py
python3 scripts/generate-release-manifest.py --output /tmp/agentickvm-public-beta-final-review-baseline-manifest.json
python3 scripts/check-public-beta.py
uv run --offline --with pytest --python python3.13 python -m pytest
```

Result summary:

- package check: passed
- package build check: passed with documented deferred status when optional
  build tooling is unavailable
- CLI smoke: passed
- lint sanity: passed
- type sanity: passed
- docs validation: passed
- site validation: passed
- release manifest generation to `/tmp`: passed
- public beta readiness check: passed
- pytest: `575 passed`

## Merge Readiness

Ready for human merge review if the maintainer accepts the current beta scope
and known limitations.

Not ready for:

- automatic merge without review
- production hardware use
- live provider smoke
- live MCP server adoption
- SDK trial adoption
- public release publication without maintainer approval

## Release Readiness

Release notes, known limitations, security statement, merge commands, Pages
enablement checklist, tagging plan, and maintainer runbook are present.

The first pre-release can be drafted after merge only if:

- CI passes on `main`
- the final validation matrix passes on `main`
- a maintainer approves the tag format
- a maintainer approves release publication
- no generated local artifacts are attached

## Security Posture

- policy remains the authority boundary
- unknown capabilities fail closed
- provider and target registries remain required
- approval-required flows remain explicit
- audit remains mandatory
- SQLite audit backend is local explicit-path only
- credentials are not resolved in tests
- secrets and credential refs are redacted
- CI remains mock-only
- Pages remains static and tracking-free
- live providers are disabled by default

## Human Decisions

Required before merge:

- approve or reject `feature/public-beta-cutover`
- decide PR-vs-local merge process
- decide whether to keep package metadata at `0.0.0` for this beta candidate
- decide whether wheel/sdist build deferral is acceptable for beta
- decide whether to enable GitHub Pages after merge

Required before pre-release:

- choose `v0.1.0-public-beta.1` or an alternate tag
- approve the release notes body
- approve publishing a GitHub pre-release
- confirm no sensitive artifacts are attached

## Exact Next Recommended Action

Open a human-reviewed PR from `feature/public-beta-cutover` to `main` using the
summary in `docs/public-beta-merge-review.md`, then wait for CI and human
approval before merging.

## Unsafe Actions Still Deferred

- live PiKVM execution
- live Redfish execution
- live provider smoke
- PiKVM keyboard, mouse, paste, or hotkey input
- Redfish reset, boot, virtual media, BIOS, firmware, storage, network, or
  account mutation
- live MCP server adoption
- Python MCP SDK mainline adoption
- in-band remote desktop/session provider implementation
- external production audit backend or SIEM integration
- unattended production hardware recovery
