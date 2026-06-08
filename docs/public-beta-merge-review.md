# Public Beta Merge Review

Branch: `feature/public-beta-cutover`

Base branch: `feature/audit-beta-readiness`

Base commit: `e1c1f6c`

## Purpose

Prepare the full public beta branch stack for human merge review, GitHub Pages
enablement, and first pre-release drafting.

This branch is not a live provider branch and not an SDK trial merge.

## Branch Stack

Recommended review order:

1. `feature/package-release-hardening`
2. `feature/agentickvm-next-10-integration`
3. `feature/audit-beta-readiness`
4. `feature/public-beta-cutover`

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
- `64336bf docs: add public beta cutover plan`
- `5f10373 docs: add public beta release notes`
- `a43a3ed docs: add public beta known limitations`
- `569252a docs: add public beta security statement`
- `ec8e3db docs: add GitHub Pages enablement checklist`
- `727c078 docs: polish public beta site content`
- `f1c0a55 docs: add maintainer public beta runbook`
- `3be8147 docs: add GitHub issue and PR templates`
- `3ab16b6 build: strengthen public beta release manifest`
- `823bf47 test: add public beta readiness check`

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

Public beta cutover:

- cutover plan with branch stack, merge order, tag proposal, Pages enablement,
  release notes workflow, rollback, and post-merge checks
- changelog entry and draft release notes for `v0.1.0-public-beta.1`
- known limitations and security statement
- GitHub Pages enablement checklist
- site public beta status and local links to release notes, limitations,
  security, and roadmap
- maintainer runbook
- issue and PR templates that warn against secrets and sensitive artifacts
- strengthened release manifest public beta fields
- `scripts/check-public-beta.py` and CI hook

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
python3 scripts/check-public-beta.py
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
- Package metadata remains `0.0.0` until a maintainer approves a version bump.

## Merge Blockers

- any failing release script or test suite
- any committed generated audit DB/export/checkpoint/approval/artifact file
- any workflow secret requirement
- any live provider command in CI
- any SDK trial dependency on this branch
- any public claim that live provider support is available today
- issue templates that request secrets or unredacted operational details
- generated release manifest or local artifacts committed to the repository

## Suggested PR

Title:

```text
Prepare AgenticKVM public beta cutover
```

Body:

```markdown
## Summary

Prepares AgenticKVM for human public beta merge review and first pre-release
drafting. This branch includes the release-quality/site/package stack,
operator approval transport, local operator console, SQLite audit backend v1,
safe recovery playbooks, live-provider preflight gates, public beta docs,
release notes, Pages enablement checklist, maintainer runbook, templates, and
public beta readiness checks.

## Safety

- no live providers implemented or enabled
- no live provider network calls
- no hardware touched
- no credentials or secrets
- no SDK trial dependency added
- no live MCP server enabled
- CI remains mock-only

## Validation

- `python3 scripts/check-package.py`
- `python3 scripts/build-package.py`
- `python3 scripts/smoke-cli.py`
- `python3 scripts/lint-sanity.py`
- `python3 scripts/type-sanity.py`
- `python3 scripts/validate-docs.py`
- `python3 scripts/check-site.py`
- `python3 scripts/generate-release-manifest.py --output <temp path>`
- `python3 scripts/check-public-beta.py`
- `uv run --offline --with pytest --python python3.13 python -m pytest`
```

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
- decide whether to use `v0.1.0-public-beta.1` or another pre-release tag
- decide whether package metadata should be bumped before tagging
- decide next live-provider planning branch, if any

## Post-Merge Checklist

- CI passes on `main`
- GitHub Pages source is set to GitHub Actions
- Pages deploy succeeds
- release manifest is generated to `/tmp` or ignored `artifacts/`
- release notes are copied into a GitHub pre-release draft
- no tag is pushed until maintainer approval
- README badges remain deferred until the public repository URL is confirmed
