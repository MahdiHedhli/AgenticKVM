# Release PR Review Package

Branch: `feature/package-release-hardening`

Base branch: `feature/release-quality-gates`

Base commit: `5656d25`

Purpose: harden the release-quality branch into a near-mergeable public release
candidate by adding package artifact verification, CLI smoke checks, lint/type
sanity gates, coverage policy, release manifest generation, CI hardening, site
preview checks, and release artifact review docs.

## Commit Summary

- `5042461 build: add package artifact verification`
- `7d900cb test: add CLI smoke matrix`
- `34b99c6 test: add lint sanity gate`
- `76b8594 test: add type sanity gate`
- `0e50aa4 docs: add coverage policy`
- `16dd8ed build: add release manifest generator`
- `07d1496 ci: harden release quality workflow`
- `9e796c6 test: add site preview checks`
- `5724d65 ci: add site preview gate`
- `3555873 docs: add release artifact checklist`
- `edf8acb docs: add release PR review package`
- final closeout commit records release readiness, checklist, roadmap, and
  heartbeat progress

## Files Changed By Category

Workflow:

- `.github/workflows/ci.yml`

Scripts:

- `scripts/build-package.py`
- `scripts/smoke-cli.py`
- `scripts/lint-sanity.py`
- `scripts/type-sanity.py`
- `scripts/generate-release-manifest.py`
- `scripts/check-site.py`

Tests:

- `tests/contract/test_package_artifacts.py`
- `tests/contract/test_cli_smoke_matrix.py`
- `tests/contract/test_lint_sanity.py`
- `tests/contract/test_type_sanity.py`
- `tests/contract/test_release_manifest.py`
- `tests/security/test_site_preview_safety.py`
- updated `tests/security/test_workflow_safety.py`

Docs:

- `docs/packaging.md`
- `docs/cli-smoke.md`
- `docs/linting.md`
- `docs/type-checking.md`
- `docs/coverage-policy.md`
- `docs/site-preview.md`
- `docs/release-artifacts.md`
- `docs/heartbeat-log.md`

## CI Changes

CI now runs:

- `python scripts/check-package.py`
- `python scripts/build-package.py`
- `python scripts/smoke-cli.py`
- `python scripts/lint-sanity.py`
- `python scripts/type-sanity.py`
- `python scripts/validate-docs.py`
- `python scripts/check-site.py`
- `python -m pytest`

The workflow still uses `contents: read` only. It does not require secrets,
provider targets, live MCP server behavior, or the SDK trial dependency.

## Safety Checks Added

- package artifact readiness reports built/deferred status
- CLI smoke matrix covers mock, fixture, denied, approval-required, and
  validation-error paths
- lint sanity catches syntax errors, debug leftovers, obvious secret-shaped
  examples, public overclaims, and trial dependency leakage
- type sanity checks key imports, dataclass annotations, JSON-safe model output,
  and no trial SDK import
- release manifest reports branch, commit, package metadata, site/workflow
  status, and safety flags
- site preview gate checks no scripts, no analytics, no remote fonts, anchors,
  conservative provider roadmap labels, and Pages workflow boundary

## Known Limitations

- `scripts/build-package.py` reports `deferred` unless the optional `build`
  module is available.
- Coverage percentage enforcement is documented but deferred until a coverage
  tool is selected.
- Full lint/type tooling is documented but deferred until dependency review.
- Public repository URL and README badges remain undecided.
- GitHub Pages settings still require human confirmation after merge.
- Live providers, live MCP server, SDK trial adoption, and production audit
  backend remain deferred.

## Merge Blockers

- Any appearance of `mcp==1.27.2` on this branch.
- Any workflow reference to `secrets.*`.
- Any live provider command or live smoke test in CI.
- Any live provider implementation.
- Any public claim that live PiKVM or Redfish support exists today.
- Any public claim that in-band remote desktop/session providers are active
  AgenticKVM roadmap scope.
- Failing local checks or CI.

## Local Verification Commands

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

Optional manifest generation:

```bash
python scripts/generate-release-manifest.py --output /tmp/agentickvm-release-manifest.json
```

## Human Decisions

- Decide whether to merge this branch.
- Decide whether to add optional build tooling and require wheel/sdist builds.
- Decide whether to adopt full lint/type tooling.
- Decide when to add coverage percentage enforcement.
- Decide public repository URL and badges.
- Confirm GitHub Pages settings after merge.

## Rollback Plan

1. Revert CI workflow hardening if CI blocks unexpectedly.
2. Revert individual script/test commits if a gate is too strict.
3. Keep safety regression tests and docs validation unless they are directly
   causing the issue.
4. Re-run all local verification commands after rollback.
5. Do not merge SDK trial work as part of rollback.

## Post-Merge Steps

1. Confirm GitHub Actions CI passes.
2. Enable or confirm GitHub Pages deployment from GitHub Actions settings.
3. Generate a release manifest into an ignored artifact path or temp path.
4. Review release artifact checklist.
5. Decide whether to add public workflow badges after a repository URL exists.

## Next-10 Integration Addendum

Branch: `feature/agentickvm-next-10-integration`

Additional safe changes on the integration branch:

- release-quality and GitHub Pages integration confirmed through the
  package-release hardening base
- Python MCP SDK trial reviewed without merging `trial/mock-only-mcp-python-sdk`
- MCP stdio mainline adoption deferred; no `mcp==1.27.2` dependency added
- local operator approval transport added with explicit queue path and optional
  audit path
- local operator console added through `agentickvm status` and
  `agentickvm console`
- SQLite audit backend v1 added with explicit-path opt-in, verification,
  listing, export, and tamper-detection tests
- live PiKVM observe, live Redfish observe, and PiKVM input-control phases
  documented as gated/deferred
- safe recovery playbook framework added with dry-run and mock/fake execution
  through `MCPRouter` and `ControlPlane`

Additional review focus:

- verify CLI approval queue paths remain explicit
- verify SQLite audit paths remain explicit
- verify playbooks do not call providers directly
- verify no SDK trial dependency appears in `pyproject.toml`
- verify no live provider or live input code was added
- verify all checks report mock-only behavior

## Audit Beta Readiness Addendum

Branch: `feature/audit-beta-readiness`

Additional safe changes:

- SQLite audit backend hardening review, checkpoint helpers, event inspection,
  checkpoint-aware export, and malformed/tamper tests
- audit CLI polish for checkpoint and inspect workflows
- approval queue audit integration hardening for denial, expiry, consumption,
  redaction, fingerprint mismatch, and malformed stores
- recovery playbook registry validation, required risk/rollback metadata,
  redacted step output, and approval/policy stop behavior
- live-provider preflight gates with CI/test-mode blocking and observe-only
  capability enforcement
- public beta readiness and risk-register docs
- release gates for beta docs, preflight docs, and generated local artifact
  exclusions

Additional review focus:

- verify no live provider network calls were added
- verify no SDK trial dependency entered this branch
- verify preflight does not instantiate providers or resolve credentials
- verify generated audit DB/export/checkpoint/approval/artifact files are not
  tracked
- verify public beta docs remain conservative about live-provider readiness

## Public Beta Cutover Addendum

Branch: `feature/public-beta-cutover`

Additional safe changes:

- public beta cutover plan
- changelog entry and draft release notes for proposed
  `v0.1.0-public-beta.1`
- public beta known limitations and security statement
- GitHub Pages enablement checklist
- public beta site copy and links
- maintainer runbook
- issue and PR templates with no-secrets warnings
- release manifest public beta fields
- public beta readiness script and CI hook

Additional review focus:

- verify issue templates do not request secrets or unredacted operational
  details
- verify release notes describe deferred live providers and SDK trial separation
- verify generated manifests are written only to temp or ignored artifact paths
- verify no tag or release has been published from this branch
