# Release Checklist

Use this checklist before merging a release-quality branch or cutting a release.

## Branch

- [ ] Branch is not `main`.
- [ ] Branch is not `trial/mock-only-mcp-python-sdk`.
- [ ] Branch does not merge SDK trial work.
- [ ] Branch has no unrelated dirty changes.
- [ ] Branch review package is complete.

## Tests

- [ ] `python scripts/check-package.py` passes.
- [ ] `python scripts/validate-docs.py` passes.
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

## Docs And Site

- [ ] README status is accurate.
- [ ] Security model is current.
- [ ] Provider contracts are current.
- [ ] Roadmap status is current.
- [ ] GitHub Pages docs are current.
- [ ] Static site has no analytics or tracking.
- [ ] Static site does not claim live PiKVM or Redfish support.
- [ ] Static site does not claim live RustDesk, VNC, RDP, or MeshCentral support.
- [ ] Static site describes future provider families as roadmap or readiness
      work only.

## Release Decision

- [ ] Human reviewer approved the branch.
- [ ] Rollback plan is understood.
- [ ] Deferred unsafe tasks are documented.
- [ ] Next recommended task is documented.
