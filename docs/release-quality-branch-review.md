# Release Quality Branch Review

Branch: `feature/release-quality-gates`

Base branch: `feature/github-pages-site`

Base commit: `796ef2a`

Purpose: add mock-only CI, static GitHub Pages deployment, package/docs/spec
validation, safety regression checks, contributor workflow docs, and release
readiness docs without adding live providers or the SDK trial dependency.

## Commit Summary

- `e0a87c3 docs: plan release quality gates`
- `9d23ad0 ci: add safe mock-only CI workflow`
- `ba398af ci: add GitHub Pages static site workflow`
- `a65febf test: add package metadata and import checks`
- `0bb5880 test: add docs and spec validation`
- `a3f12e5 test: add release safety regression suite`
- `26766b9 docs: add development and testing guide`
- `9916bc1 docs: add release readiness checklist`
- `6df4f1a docs: polish README release links`
- `7e3101c docs: add release quality branch review package`
- final closeout commit records roadmap and heartbeat progress

## Files Changed

Workflow files:

- `.github/workflows/ci.yml`
- `.github/workflows/pages.yml`

Validation scripts:

- `scripts/check-package.py`
- `scripts/validate-docs.py`

Tests:

- `tests/contract/test_package_metadata.py`
- `tests/contract/test_docs_validation.py`
- `tests/security/test_workflow_safety.py`
- `tests/security/test_release_safety_regressions.py`
- updated `tests/security/test_github_pages_site_safety.py`

Docs and top-level guidance:

- `README.md`
- `CONTRIBUTING.md`
- `docs/development.md`
- `docs/testing.md`
- `docs/packaging.md`
- `docs/release-quality-gates.md`
- `docs/release-readiness.md`
- `docs/release-checklist.md`
- `docs/github-pages.md`
- `docs/heartbeat-log.md`

## CI Workflow Added

The CI workflow runs on pull requests and pushes to `main`.

It uses `contents: read` permissions only and runs:

- package metadata validation
- docs/spec validation
- pytest

The workflow does not reference GitHub Actions secrets, provider smoke tests,
live hardware, live MCP server behavior, or the trial-only MCP SDK dependency.

## Pages Workflow Added

The Pages workflow runs on pushes to `main` and `workflow_dispatch`.

It uses:

- `contents: read`
- `pages: write`
- `id-token: write`

It uploads only `site/` through official GitHub Pages actions. It does not
install dependencies, run tests, require secrets, use analytics, or invoke live
provider behavior.

Repository settings may still need GitHub Pages enabled before deployment works.

## Tests Added

Package and docs checks:

- package metadata, importability, CLI entry-point metadata, and no SDK trial
  dependency
- required docs/spec/site files
- key safety language
- local markdown links
- public overclaim checks

Workflow safety checks:

- minimal CI permissions
- Pages publishes static `site/` only
- no secrets
- no live provider references
- no trial MCP SDK dependency

Release safety regressions:

- unknown capability/provider/target fail closed
- disabled provider/target fail closed
- hard invariant MCP tools denied
- audit and emergency stop disabling denied
- live provider placeholders disabled
- PiKVM and Redfish live configs rejected by default
- MCP/SDK/host layers keep provider execution behind `ControlPlane`
- public site and package metadata avoid live-support overclaims

## Risks Closed

- CI behavior is now explicit and mock-only.
- Static Pages deployment path is documented and constrained to `site/`.
- Package metadata drift has a local validation script.
- Docs/spec/site existence and local links have validation coverage.
- Public overclaim phrases have automated checks.
- Release safety invariants have a single regression suite.
- Contributor workflow and testing expectations are documented.

## Risks Open

- GitHub Pages repository settings still need human confirmation.
- Package wheel/sdist build is documented but not yet enforced by a build job.
- Mainline dependency policy remains simple because the project currently has no
  runtime dependencies.
- Live MCP server remains deferred.
- Live PiKVM, Redfish, and remote-session providers remain deferred.
- Production audit backend remains deferred.

## Human Decisions Required

- Decide whether to merge this release-quality branch.
- Confirm GitHub Pages settings after merge.
- Decide when to add package build verification beyond metadata/import checks.
- Decide whether CI should later add lint/type checks.
- Decide whether status badges should be added after a remote repository URL is
  configured.

## Merge Checklist

- Run `python scripts/check-package.py`.
- Run `python scripts/validate-docs.py`.
- Run `uv run --offline --with pytest --python python3.13 python -m pytest`.
- Confirm no `mcp==1.27.2` dependency entered this branch.
- Confirm no live provider code or config was added.
- Confirm no GitHub Actions secrets are required.
- Confirm public site copy stays conservative about live provider support.

## Rollback Plan

If workflows create a problem after merge:

1. Disable the affected workflow in GitHub or revert the workflow commit.
2. Revert release-quality commits in reverse order if needed.
3. Re-run package, docs, and pytest checks.
4. Keep the SDK trial dependency isolated from mainline branches.

If docs validation blocks unrelated docs changes, tune `scripts/validate-docs.py`
with a focused follow-up rather than removing the release gate.
