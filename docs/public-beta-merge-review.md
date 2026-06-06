# Public Beta Merge Review

Branch: `feature/audit-beta-readiness`

Base branch: `feature/agentickvm-next-10-integration`

Base commit: `952e244`

## Purpose

Prepare the next-10 integration branch for human public beta review by
hardening local SQLite audit behavior, approval/audit integration, recovery
playbook safety, live-provider preflight gates, and release-quality checks.

This branch is not a live provider branch and not an SDK trial merge.

## Branch Stack

Recommended review order:

1. `feature/package-release-hardening`
2. `feature/agentickvm-next-10-integration`
3. `feature/audit-beta-readiness`

The SDK trial branch remains separate:

- `trial/mock-only-mcp-python-sdk`
- trial dependency `mcp==1.27.2`
- not merged into this branch

## Commit Summary

- `dec402c test: harden SQLite audit backend`
- `38e56e2 feat: polish audit CLI workflows`
- `cc02a09 test: harden approval queue audit integration`
- `dd33af0 test: harden recovery playbook safety`
- `a173505 feat: add live provider preflight gates`
- `5081a51 docs: add public beta risk register`
- `4a602fe docs: add public beta readiness checklist`
- `6139844 ci: add audit beta readiness gates`

Later closeout commits may update roadmap, heartbeat, and final validation
status.

## Major Changes

SQLite audit:

- checkpoint creation and verification helpers
- event inspection helper
- export support with checkpoint metadata
- reopen, tamper, deletion, malformed DB, checkpoint, and export tests
- SQLite audit backend hardening docs and contract

Audit CLI:

- `agentickvm audit checkpoint`
- `agentickvm audit inspect`
- checkpoint-aware SQLite export
- failure exit codes for invalid audit verification

Approval queue:

- denial and expiry audit event coverage
- redacted approval preview/reason tests
- fingerprint mismatch tests
- hard-invariant approval rejection tests
- malformed approval store fail-closed tests

Recovery playbooks:

- registry validation for known tool and declared capability mapping
- required risk tier and rollback notes
- redacted step payload output
- approval-required stop behavior tests
- policy denial preservation tests

Live-provider preflight:

- pure local preflight model
- `agentickvm providers preflight`
- CI/test-mode blocking
- explicit external config, audit, approval, credential-ref, TLS, timeout,
  artifact, and manual-smoke evidence
- observe-only capability enforcement
- no provider transport creation or credential resolution

Release gates:

- docs/spec validation requires beta, preflight, approval queue, recovery, and
  SQLite hardening docs
- lint sanity rejects committed generated SQLite DBs, audit exports,
  checkpoints, approval queues, screenshots, and local artifacts
- release manifest reports beta/preflight/audit gate status
- CI generates a release manifest into ignored `artifacts/`

## Safety Review Focus

Reviewers should confirm:

- no live provider code executes
- no live provider is enabled by default
- no SDK trial dependency appears in `pyproject.toml`
- preflight blocks CI and pytest mode
- CLI preflight does not create audit or approval files while checking gates
- SQLite audit paths are explicit
- approval queue paths are explicit
- playbooks route through `MCPRouter` and `ControlPlane`
- generated local audit/artifact files are not tracked
- public docs avoid live-provider support claims

## Required Local Verification

Run before merge review:

```bash
python3 scripts/check-package.py
python3 scripts/build-package.py
python3 scripts/smoke-cli.py
python3 scripts/lint-sanity.py
python3 scripts/type-sanity.py
python3 scripts/validate-docs.py
python3 scripts/check-site.py
python3 scripts/generate-release-manifest.py --output /tmp/agentickvm-release-manifest.json
uv run --offline --with pytest --python python3.13 python -m pytest
```

## Known Limitations

- The Python MCP SDK trial remains held outside this branch.
- Live PiKVM and Redfish execution remain deferred.
- Live provider preflight is a readiness gate only, not operator approval.
- SQLite audit backend v1 is local and explicit-path only.
- External production audit backend and SIEM integration remain deferred.
- GitHub Pages settings still require human enablement after merge.
- Wheel/sdist build remains documented/deferred if the optional build module is
  unavailable.

## Merge Blockers

- any failing release script or test suite
- any committed generated audit DB/export/checkpoint/approval/artifact file
- any workflow secret requirement
- any live provider command in CI
- any SDK trial dependency on this branch
- any public claim that live provider support is available today

## Rollback Plan

1. Revert this branch from newest commit to oldest if a beta gate is too strict.
2. Keep release-quality and package-hardening branches intact.
3. Keep SDK trial branch separate.
4. Re-run release scripts and pytest after rollback.

## Human Decisions

- decide whether this branch is ready for public beta PR review
- decide whether local SQLite audit v1 is sufficient for beta scope
- decide whether GitHub Pages should be enabled from Actions
- decide whether to keep build artifact generation deferred
- decide next live-provider planning branch, if any
