# Maintainer Public Beta Runbook

This runbook is for maintainers reviewing, merging, and preparing an
AgenticKVM public beta pre-release. It does not authorize live hardware use.

## Validate The Branch

Run from the candidate branch:

```bash
git status --short --branch
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

If `scripts/check-public-beta.py` is not present yet, use the rest of the matrix
and treat the script as a deferred gate until added.

## Review The Branch Stack

Expected stack:

1. `feature/github-pages-site`
2. `feature/release-quality-gates`
3. `feature/package-release-hardening`
4. `feature/agentickvm-next-10-integration`
5. `feature/audit-beta-readiness`
6. `feature/public-beta-cutover`

Confirm the final branch includes the stack and does not include:

- `trial/mock-only-mcp-python-sdk`
- `mcp==1.27.2`
- live provider code execution
- committed generated audit DBs, manifests, screenshots, approval queues, or
  artifacts

## Merge

1. Open a PR from `feature/public-beta-cutover` to `main`.
2. Include the public beta merge review package in the PR body.
3. Wait for CI.
4. Review docs, scripts, workflows, site, and tests.
5. Merge only after human approval.

Do not fast-forward or force-push over review history unless the maintainer has
an explicit local policy for that operation.

## Enable GitHub Pages

After merge:

1. Open repository settings.
2. Go to Pages.
3. Select GitHub Actions as the source.
4. Confirm the Pages workflow publishes only `site/`.
5. Confirm no secrets are required.
6. Run `python3 scripts/check-site.py` locally if site copy changes.

Use `docs/github-pages-enablement-checklist.md` for the full checklist.

## Cut A Pre-Release Tag

Suggested tag:

```bash
git tag -a v0.1.0-public-beta.1 -m "AgenticKVM public beta 0.1.0"
```

Do not push tags until the release notes, changelog, manifest, and CI status
are reviewed.

Suggested release notes source:

- `docs/releases/public-beta-0.1.0.md`

## Generate Release Manifest

Generate to `/tmp` or ignored `artifacts/`:

```bash
python3 scripts/generate-release-manifest.py --output /tmp/agentickvm-public-beta-manifest.json
```

Do not commit generated manifests unless a future release process explicitly
changes that policy.

## Inspect Audit Store Locally

For local temp-path audit stores only:

```bash
agentickvm --audit-sqlite-path /tmp/agentickvm-audit.sqlite call --target mock-host --tool get_power_state
agentickvm audit verify --sqlite-path /tmp/agentickvm-audit.sqlite
agentickvm audit list --sqlite-path /tmp/agentickvm-audit.sqlite
agentickvm audit checkpoint --sqlite-path /tmp/agentickvm-audit.sqlite --audit-log-id public-beta-review --output /tmp/agentickvm-audit-checkpoint.json
```

Do not use real provider targets or credentials during public beta validation.

## Check For Secrets And Artifacts

Run:

```bash
python3 scripts/lint-sanity.py
git status --short
git ls-files | grep -E '(\.sqlite$|\.db$|screenshot|approval.*\.json|audit.*export|checkpoint.*\.json)' && exit 1 || true
```

Do not paste secrets, real hostnames, real IP addresses, screenshots, audit
databases, approval queues, or generated artifacts into issues or PRs.

## Rollback

If a public beta merge causes issues:

1. Revert the merge commit or revert the problematic commits.
2. Disable Pages if the site output is wrong.
3. Keep `trial/mock-only-mcp-python-sdk` separate.
4. Re-run the full local validation matrix.
5. Publish a follow-up note if a pre-release was already drafted.

## SDK Trial Separation

The SDK trial branch remains separate until a human review explicitly accepts
it. Public beta cutover must not add `mcp==1.27.2`, live MCP server behavior, or
SDK-backed provider access to mainline.
