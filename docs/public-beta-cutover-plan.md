# Public Beta Cutover Plan

This plan prepares AgenticKVM for a safe public beta merge and first tagged
pre-release. It does not approve a merge to `main`, publish a release, push a
tag, or authorize live hardware use.

## Branch Stack

Current cutover branch:

- `feature/public-beta-cutover`

Expected branch stack:

1. `feature/github-pages-site`
2. `feature/release-quality-gates`
3. `feature/package-release-hardening`
4. `feature/agentickvm-next-10-integration`
5. `feature/audit-beta-readiness`
6. `feature/public-beta-cutover`

The branches are intended to be stacked. Before merge, confirm ancestry with:

```bash
git merge-base --is-ancestor feature/github-pages-site feature/public-beta-cutover
git merge-base --is-ancestor feature/release-quality-gates feature/public-beta-cutover
git merge-base --is-ancestor feature/package-release-hardening feature/public-beta-cutover
git merge-base --is-ancestor feature/agentickvm-next-10-integration feature/public-beta-cutover
git merge-base --is-ancestor feature/audit-beta-readiness feature/public-beta-cutover
```

If the branch stack has diverged, stop and review the diff instead of merging by
guesswork.

## Merge Strategy

Recommended approach:

1. Open a PR from `feature/public-beta-cutover` to `main`.
2. In the PR body, explain that the branch includes the reviewed stack above.
3. Confirm all local checks pass.
4. Confirm GitHub Actions CI passes.
5. Confirm the diff does not include the SDK trial dependency.
6. Confirm the diff does not include live provider behavior.
7. Confirm public docs do not overclaim live support.
8. Merge only after human approval.

Do not merge `trial/mock-only-mcp-python-sdk` as part of this cutover.

## Validation Commands

Run locally before PR review:

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

If `scripts/check-public-beta.py` has not yet been added, defer that command
until the readiness script lands.

## GitHub Pages Enablement

After merge to `main`, enable Pages only through GitHub Actions:

1. Open repository settings.
2. Go to Pages.
3. Set source to GitHub Actions.
4. Confirm `.github/workflows/pages.yml` publishes only `site/`.
5. Confirm no secrets are required.
6. Confirm no analytics, tracking, provider config, credentials, or live smoke
   appears in the site or workflow.

Pages enablement is a human repository setting change, not an automated step in
this sprint.

## Tag Naming Proposal

Preferred first pre-release tag:

- `v0.1.0-public-beta.1`

Alternative if Python-package style pre-release naming is preferred later:

- `v0.1.0a1`

Do not create or push a tag without explicit maintainer instruction.

## Release Notes Workflow

1. Finalize `docs/releases/public-beta-0.1.0.md`.
2. Update `CHANGELOG.md`.
3. Generate a release manifest to `/tmp` or ignored `artifacts/`.
4. Copy the release notes into the GitHub pre-release draft.
5. Attach no audit DBs, screenshots, credentials, approval queues, or generated
   local artifacts.
6. Mark the release as a pre-release.

## What Remains Disabled

- live PiKVM provider execution
- live Redfish provider execution
- PiKVM input control
- live MCP server
- Python MCP SDK dependency on mainline
- in-band remote desktop/session providers; that scope is parked outside the
  AgenticKVM roadmap
- production external audit backend and SIEM integration
- provider mutation actions against real hardware

## Rollback Plan

If the public beta cutover branch causes issues:

1. Revert the merge commit or close the PR without merge.
2. Disable the Pages workflow if it created unexpected output.
3. Keep `main` free of the SDK trial dependency.
4. Re-run all release checks after rollback.
5. Do not delete audit, approval, or review docs unless a replacement plan is
   reviewed.

## Post-Merge Checks

After merge:

- CI passes on `main`
- Pages deploy completes from GitHub Actions
- site has no tracking or unsupported live-provider claims
- release manifest can be generated to a safe path
- README and roadmap match release status
- GitHub issue templates do not ask for secrets
- no generated audit/artifact files are present in the repository

## Human Decisions Required

- approve or reject public beta merge
- choose pre-release tag format
- decide whether to enable GitHub Pages after merge
- decide whether to publish a GitHub pre-release
- decide whether build artifact generation may remain deferred
- decide next branch: live-provider implementation planning, audit backend
  planning, or SDK trial review
