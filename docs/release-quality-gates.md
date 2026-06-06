# Release Quality Gates Plan

## Purpose

Move AgenticKVM from a well-tested prototype repository toward a more
production-quality open-source project scaffold without implementing live
providers, live MCP server behavior, or trial SDK dependencies.

## Goals

- Add mock-only CI that can run safely on GitHub Actions.
- Add static GitHub Pages deployment for `site/`.
- Verify package metadata, imports, and CLI entry-point declarations.
- Validate required docs, specs, site files, and safety language.
- Add release safety regression checks for provider, target, policy, audit, and
  workflow invariants.
- Document developer workflow, testing workflow, packaging expectations, and
  release readiness.
- Create a human-review package for this branch.

## Non-Goals

- No live providers.
- No live MCP server.
- No SDK trial merge.
- No `mcp==1.27.2` dependency.
- No real hardware tests.
- No credential resolution.
- No external service tests.
- No analytics or tracking.
- No workflow secrets.

## Branch Strategy

This work is on `feature/release-quality-gates`, created from
`feature/github-pages-site`. It must not be performed on `main` or
`trial/mock-only-mcp-python-sdk`.

The branch may be reviewed later and merged only after human review confirms:

- no trial SDK dependency is present
- CI is mock-only
- Pages workflow publishes static files only
- release checks do not create live provider access

## CI Strategy

The CI workflow should run on pull requests and pushes to `main` with minimal
permissions:

- `contents: read`

CI may install Python dependencies from package indexes because GitHub-hosted
runners need dependencies, but tests must remain mock-only and must not make
live provider, hardware, or credential calls.

The workflow should run:

- `python scripts/check-package.py`
- `python scripts/build-package.py`
- `python scripts/smoke-cli.py`
- `python scripts/lint-sanity.py`
- `python scripts/type-sanity.py`
- `python scripts/validate-docs.py`
- `python scripts/check-site.py`
- `python -m pytest`

CI must not:

- reference secrets
- reference real provider endpoints
- run live smoke tests
- start a live MCP server
- use SDK trial dependency

## GitHub Pages Strategy

The Pages workflow should publish only the static `site/` directory.

Allowed workflow behavior:

- runs on push to `main` and `workflow_dispatch`
- uses official GitHub Pages actions
- uploads `site/`
- deploys the Pages artifact
- uses minimal permissions:
  - `contents: read`
  - `pages: write`
  - `id-token: write`

Disallowed workflow behavior:

- secrets
- analytics or tracking
- provider tests
- live hardware calls
- dependency install
- SDK trial dependency
- external deployment tokens

## Package And Build Strategy

This branch should verify package readiness without adding risky build
dependencies.

Minimum checks:

- `pyproject.toml` metadata is present.
- package imports from `src/agentickvm`.
- CLI entry point is declared and importable.
- trial-only `mcp==1.27.2` is absent.
- package discovery points to `src`.
- source tree does not require live provider dependencies by default.

If build tooling is already available, a future branch may add wheel/sdist
build verification. If not, document the future build command instead of
adding dependencies just for this sprint.

## Docs And Spec Validation Strategy

Add a lightweight script that validates:

- required docs exist
- required specs exist
- control-plane contracts exist
- GitHub Pages site files exist
- README links to key docs
- local markdown links are not obviously broken
- required safety language exists
- forbidden overclaim phrases are absent

The script must be dependency-free and safe to run in CI.

## Safety Regression Strategy

Add tests that pin release-critical invariants:

- unknown provider fails closed
- unknown target fails closed
- disabled provider fails closed
- disabled target fails closed
- raw secret reveal denied
- policy modification denied
- audit disabling denied
- emergency stop disabling denied
- real provider placeholders disabled
- PiKVM/Redfish live configs remain disabled by default
- workflows use no secrets
- workflows do not run live provider commands
- no trial SDK dependency appears in package metadata
- site does not overclaim live provider support

## Release-Readiness Gates

Before a release or public beta:

- tests pass locally and in CI
- package checks pass
- docs/spec validation passes
- site safety checks pass
- no trial SDK dependency
- no live provider enabled by default
- no secrets in repo config, docs, workflows, or site files
- release notes and roadmap are reviewed
- human release approval is recorded

## Human Decisions Needed

- Whether to merge this release-quality branch.
- Whether GitHub Pages should publish from the workflow added here.
- Whether future packaging should commit a lockfile, constraints file, or
  dependency report.
- Whether to add wheel/sdist build tooling in a future branch.
- What public repository URL should be used in the site footer.

## Risks

- CI dependency installation requires network access to package indexes on
  hosted runners, even though tests remain mock-only.
- Pages deployment publishes public content on pushes to `main` if enabled by
  repository settings.
- Additional package/build tooling could create unnecessary dependency churn if
  added too early.
- Release docs may be mistaken for live-provider readiness unless they clearly
  say live providers remain deferred.
