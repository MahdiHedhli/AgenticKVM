# Public Beta Merge Command Plan

This plan is for a human maintainer. Do not run these commands unless the
public beta candidate has been reviewed and explicitly approved for merge.

## Preconditions

- Candidate branch: `feature/public-beta-cutover`
- Target branch: `main`
- Expected candidate commit at the time of final review: `69732c8` or later
- No SDK trial branch merge
- No release tag push
- No GitHub release publication
- No GitHub Pages settings change from the command line
- No live provider smoke

## Pre-Merge Validation

Run from `feature/public-beta-cutover`:

```bash
git checkout feature/public-beta-cutover
git status --short --branch
git merge-base --is-ancestor feature/github-pages-site feature/public-beta-cutover
git merge-base --is-ancestor feature/release-quality-gates feature/public-beta-cutover
git merge-base --is-ancestor feature/package-release-hardening feature/public-beta-cutover
git merge-base --is-ancestor feature/agentickvm-next-10-integration feature/public-beta-cutover
git merge-base --is-ancestor feature/audit-beta-readiness feature/public-beta-cutover
python3 scripts/check-package.py
python3 scripts/build-package.py
python3 scripts/smoke-cli.py
python3 scripts/lint-sanity.py
python3 scripts/type-sanity.py
python3 scripts/validate-docs.py
python3 scripts/check-site.py
python3 scripts/generate-release-manifest.py --output /tmp/agentickvm-public-beta-merge-manifest.json
python3 scripts/check-public-beta.py
uv run --offline --with pytest --python python3.13 python -m pytest
```

Stop if any command fails.

## Recommended Merge Strategy

Preferred approach for public review:

1. Push `feature/public-beta-cutover` only after review, if a remote exists.
2. Open a pull request from `feature/public-beta-cutover` to `main`.
3. Let CI run.
4. Review the full branch stack in the PR.
5. Merge through the hosting platform after approval.

This preserves review metadata and avoids accidental local-only merges.

## Local Merge Alternative

If the maintainer explicitly chooses a local merge:

```bash
git checkout main
git status --short --branch
git merge --no-ff feature/public-beta-cutover
```

Use a merge commit rather than a silent fast-forward if the maintainer wants the
public beta cutover to remain visible as one reviewed integration point. A
fast-forward merge is also technically possible because the local stack is
linear from `main`, but it hides the final cutover boundary.

## Conflict Handling Rule

If a conflict appears:

1. Stop.
2. Do not resolve by deleting safety docs, specs, tests, workflows, or release
   gates.
3. Inspect the conflict against the constitution and public beta docs.
4. Resolve conservatively.
5. Re-run the full validation matrix.
6. Commit the conflict resolution only after review.

## Post-Merge Validation

Run from `main` after the merge:

```bash
git checkout main
git status --short --branch
python3 scripts/check-package.py
python3 scripts/build-package.py
python3 scripts/smoke-cli.py
python3 scripts/lint-sanity.py
python3 scripts/type-sanity.py
python3 scripts/validate-docs.py
python3 scripts/check-site.py
python3 scripts/generate-release-manifest.py --output /tmp/agentickvm-public-beta-post-merge-manifest.json
python3 scripts/check-public-beta.py
uv run --offline --with pytest --python python3.13 python -m pytest
```

Verify after merge:

- `pyproject.toml` still has no `mcp` dependency.
- Live providers remain disabled by default.
- CI workflow still uses no secrets and no live provider commands.
- Pages workflow still publishes only `site/`.
- No generated audit DBs, manifests, screenshots, approval queues, or artifacts
  are tracked.

## Push Placeholder

Do not push unless the maintainer explicitly approves it.

```bash
git push <remote> main
```

If the branch needs to be pushed for PR review:

```bash
git push <remote> feature/public-beta-cutover
```

## Rollback Plan

If the local merge is not pushed:

```bash
git checkout main
git reset --hard ORIG_HEAD
```

Use this only before pushing and only after confirming `ORIG_HEAD` points to the
pre-merge `main` commit.

If the merge has already been pushed, prefer a revert commit:

```bash
git checkout main
git revert -m 1 <merge-commit>
```

After rollback, re-run the post-merge validation matrix and document the reason
for rollback in the PR or release notes.
