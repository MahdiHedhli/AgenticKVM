# Public Beta Tagging Plan

This plan describes how a maintainer may tag the first AgenticKVM public beta
pre-release after merge approval. It does not authorize creating, pushing, or
publishing a tag.

## Proposed Tag

Preferred tag:

- `v0.1.0-public-beta.1`

Alternative if the project chooses Python pre-release spelling later:

- `v0.1.0a1`

The release notes currently use `v0.1.0-public-beta.1` as the proposed tag.
Package metadata still reports `0.0.0` until a maintainer explicitly approves a
version bump.

## Tag Message Draft

```text
AgenticKVM public beta 0.1.0
```

## Release Title Draft

```text
AgenticKVM Public Beta 0.1.0
```

## Release Body Source

Use:

- `docs/releases/public-beta-0.1.0.md`

Do not attach generated audit databases, generated manifests, screenshots,
approval queue files, credentials, real hostnames, real IP addresses, or other
local artifacts to the release.

## Pre-Tag Validation

Run from `main` after the approved public beta merge:

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
python3 scripts/generate-release-manifest.py --output /tmp/agentickvm-public-beta-tag-manifest.json
python3 scripts/check-public-beta.py
uv run --offline --with pytest --python python3.13 python -m pytest
```

Stop if any check fails.

## Tag Commands

Do not run these commands without explicit maintainer approval.

```bash
git tag -a v0.1.0-public-beta.1 -m "AgenticKVM public beta 0.1.0"
```

Review the local tag:

```bash
git show v0.1.0-public-beta.1
```

Push only after explicit approval:

```bash
git push <remote> v0.1.0-public-beta.1
```

## Rollback Local Tag

If the tag was created locally but not pushed:

```bash
git tag -d v0.1.0-public-beta.1
```

If the tag was pushed by mistake, coordinate with maintainers before deleting a
remote tag:

```bash
git push <remote> :refs/tags/v0.1.0-public-beta.1
```

Remote tag deletion should be treated as a public-release incident if anyone may
have consumed the tag.

## GitHub Release Draft

After pushing the approved tag, create a GitHub pre-release draft:

1. Select the approved tag.
2. Use the release title above.
3. Paste the body from `docs/releases/public-beta-0.1.0.md`.
4. Mark the release as a pre-release.
5. Attach no sensitive local artifacts.
6. Confirm the release notes still say live providers and live MCP server are
   deferred.

Publishing the GitHub release requires explicit maintainer approval separate
from local validation.
