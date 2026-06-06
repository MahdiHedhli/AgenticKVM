# Public Beta Readiness

This checklist defines what must be true before the
`feature/agentickvm-next-10-integration` branch stack can be reviewed as a
public beta candidate. It does not approve production operation or unattended
live provider use.

## Current Beta Scope

Included in the beta candidate:

- mock-first control plane, policy, approval, and audit flows
- provider and target registries
- CLI mock/fixture workflows
- local operator approval queue
- local operator console/status output
- SQLite audit backend v1 with local explicit paths
- safe recovery playbook framework using mock/fake providers
- static GitHub Pages site
- release-quality scripts and CI workflow
- live-provider preflight gates

Deferred from beta:

- live PiKVM network transport execution
- live Redfish network transport execution
- live MCP server adoption
- Python MCP SDK dependency on mainline
- live remote desktop providers
- PiKVM live input control
- production external audit backend or SIEM integration

## Required Local Checks

Before human beta review, run:

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

The manifest path must be outside the repository unless the generated output is
explicitly ignored and treated as a release artifact.

## Safety Gates

Public beta review requires:

- CI remains mock-only
- no secrets are committed
- no SDK trial dependency is added
- no live provider is enabled by default
- approval transport tests pass
- audit backend tests pass
- audit checkpoint/export tests pass
- playbook safety tests pass
- live-provider preflight tests pass
- public docs avoid live support overclaims
- generated audit DBs, exports, checkpoints, approval queues, and artifacts are
  not committed

## Live Provider Gate

Live PiKVM and Redfish work cannot proceed until:

- preflight passes outside CI/test mode
- external lab config is operator supplied
- credential strategy is selected
- audit backend is configured
- approval transport is configured
- artifact path policy is configured where needed
- TLS and timeout policy reviews are complete
- manual smoke checklist is accepted
- human operator approval is recorded

Automated tests must continue to block live-provider preflight.

## Human Decisions

Before public beta merge:

- confirm branch stack and merge order
- review the public beta risk register
- accept current local SQLite audit limitations
- decide whether GitHub Pages should be enabled from Actions
- confirm README/site wording
- confirm rollback plan
- decide whether this is a beta candidate or should remain held

## Current Recommendation

Ready for human public beta merge review after all local checks and CI pass.
Not ready for production operation or live-provider smoke.
