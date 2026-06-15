# Public Beta Readiness

Public beta is deferred behind the killer demo: an agent recovering a real
wedged machine through the full approval chain.

The existing release-quality checks remain useful preparation, but a mock-only
conformance package is not the launch gate.

## Current Pre-Beta Scope

Available today as foundation work:

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

Required before public beta:

- Approval Broker v1 with broker-owned signed grants
- out-of-band approval channel with signed Allow/Deny grants
- official MCP SDK stdio server path after approval broker review
- live PiKVM observe-only slice behind preflight and manual smoke gates
- killer demo using the full approval chain against a real wedged machine

Deferred from public beta and launch:

- live PiKVM network transport execution
- live Redfish network transport execution
- live MCP server adoption
- Python MCP SDK dependency on mainline
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

Before public beta launch:

- confirm the killer demo evidence
- confirm signed-grant approval broker behavior
- confirm live PiKVM observe manual smoke results
- review the public beta risk register
- accept current local SQLite audit limitations
- decide whether GitHub Pages should be enabled from Actions
- confirm README/site wording
- confirm rollback plan
- decide whether public beta should proceed

## Current Recommendation

Hold public beta until the killer demo exists. Continue using this checklist for
pre-beta readiness, docs accuracy, and release-quality validation.
