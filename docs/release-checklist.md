# Release Checklist

Use this checklist before merging a release-quality branch or cutting a release.

## Branch

- [ ] Branch is not `main`.
- [ ] Branch is not `trial/mock-only-mcp-python-sdk`.
- [ ] Branch does not merge SDK trial work.
- [ ] Branch has no unrelated dirty changes.
- [ ] Branch review package is complete.
- [ ] Public beta risk register is reviewed.
- [ ] Public beta readiness checklist is reviewed.

## Tests

- [ ] `python scripts/check-package.py` passes.
- [ ] `python scripts/build-package.py` passes with `built` or documented
      `deferred` status.
- [ ] `python scripts/smoke-cli.py` passes.
- [ ] `python scripts/lint-sanity.py` passes.
- [ ] `python scripts/type-sanity.py` passes.
- [ ] `python scripts/validate-docs.py` passes.
- [ ] `python scripts/check-site.py` passes.
- [ ] `uv run --offline --with pytest --python python3.13 python -m pytest`
      passes, or fallback is documented.
- [ ] CI passes.
- [ ] No test requires real hardware, live provider network, credentials,
      external services, remote desktop software, production audit store, or
      long-running MCP host.

## Safety

- [ ] Unknown capabilities fail closed.
- [ ] Unknown providers fail closed.
- [ ] Unknown targets fail closed.
- [ ] Disabled providers fail closed.
- [ ] Disabled targets fail closed.
- [ ] Raw secret reveal is denied by default.
- [ ] Policy modification is denied.
- [ ] Audit disabling is denied.
- [ ] Emergency stop disabling is denied.
- [ ] Real provider placeholders remain disabled by default.
- [ ] Live PiKVM and Redfish configs are rejected by default.
- [ ] CLI, MCP, SDK adapter, and host paths preserve `ControlPlane`.
- [ ] Approval and audit behavior is not weakened.
- [ ] SQLite audit backend uses explicit paths only.
- [ ] Live-provider preflight blocks CI/test mode.
- [ ] Playbooks route through the MCP router and `ControlPlane`.
- [ ] Generated audit DBs, audit exports, checkpoints, approval queues,
      screenshots, and artifacts are not committed.

## Workflows

- [ ] CI workflow uses minimal permissions.
- [ ] Pages workflow uses minimal permissions.
- [ ] Workflows do not reference `secrets.*`.
- [ ] Workflows do not run live provider smoke tests.
- [ ] Workflows do not run live MCP server behavior.
- [ ] Pages workflow publishes only static `site/`.
- [ ] No GitHub Actions secret is required.

## Package

- [ ] Package metadata is intentional.
- [ ] CLI entry point metadata is present.
- [ ] Mainline branch does not include `mcp==1.27.2`.
- [ ] No trial-only dependency was added.
- [ ] Package build verification is complete or future build command is
      documented.
- [ ] Release manifest can be generated to an explicit safe path.
- [ ] Release artifact checklist is reviewed.
- [ ] Public beta merge review package is reviewed if this is a beta branch.

## Docs And Site

- [ ] README status is accurate.
- [ ] Security model is current.
- [ ] Provider contracts are current.
- [ ] Roadmap status is current.
- [ ] Public beta readiness and risk-register docs are current.
- [ ] Live-provider preflight docs are current.
- [ ] GitHub Pages docs are current.
- [ ] Static site has no analytics or tracking.
- [ ] Static site does not claim live PiKVM or Redfish support.
- [ ] Static site does not put in-band remote desktop/session providers on the
      active AgenticKVM roadmap.
- [ ] Static site describes future provider families as roadmap or readiness
      work only.

## Release Decision

- [ ] Human reviewer approved the branch.
- [ ] Rollback plan is understood.
- [ ] Deferred unsafe tasks are documented.
- [ ] Next recommended task is documented.
