# Release Artifact Checklist

Use this checklist before publishing a release artifact or approving a
release-quality branch.

## Package Artifacts

- [ ] `python scripts/check-package.py` passes.
- [ ] `python scripts/build-package.py` reports `built` or a documented
      `deferred` status.
- [ ] If `--require-build` is enabled, wheel and sdist build successfully.
- [ ] Package name is `agentickvm`.
- [ ] Package version is intentional.
- [ ] CLI entry point is declared.
- [ ] Package metadata does not include `mcp==1.27.2`.
- [ ] Package metadata does not claim live provider support.
- [ ] Generated audit/artifact paths are not included in package artifacts.
- [ ] No secrets or local credentials are included.

## Release Manifest

- [ ] `python scripts/generate-release-manifest.py --output <explicit-temp-or-artifact-path>`
      succeeds.
- [ ] Manifest includes project name and version.
- [ ] Manifest includes branch and commit.
- [ ] Manifest reports live providers enabled: `false`.
- [ ] Manifest reports SDK trial dependency present: `false`.
- [ ] Manifest reports credential refs resolved: `false`.
- [ ] Manifest is JSON-safe.
- [ ] Manifest is written only to an explicit path.

## Docs And Specs

- [ ] `python scripts/validate-docs.py` passes.
- [ ] Required specs exist.
- [ ] Required docs exist.
- [ ] Local markdown links resolve.
- [ ] Security model is current.
- [ ] Roadmap status is current.
- [ ] Release readiness docs are current.
- [ ] Coverage policy is current.

## Site

- [ ] `python scripts/check-site.py` passes.
- [ ] Static site has no scripts.
- [ ] Static site has no analytics or tracking.
- [ ] Static site has no remote fonts.
- [ ] Static site does not overclaim live provider support.
- [ ] Provider roadmap labels are conservative.
- [ ] Pages workflow publishes only `site/`.

## CI And Workflows

- [ ] CI passes.
- [ ] CI runs package, artifact, CLI smoke, lint, type, docs, site, and pytest
      gates.
- [ ] Workflows require no secrets.
- [ ] Workflows do not run live provider smoke tests.
- [ ] Workflows do not start a live MCP server.
- [ ] Pages workflow uses minimal Pages permissions.

## Safety Verification

- [ ] `python scripts/smoke-cli.py` passes.
- [ ] `python scripts/lint-sanity.py` passes.
- [ ] `python scripts/type-sanity.py` passes.
- [ ] `uv run --offline --with pytest --python python3.13 python -m pytest`
      passes.
- [ ] Unknown providers, targets, and capabilities fail closed.
- [ ] Real provider placeholders remain disabled.
- [ ] Live PiKVM and Redfish configs remain rejected by default.
- [ ] Raw secret reveal remains denied by default.
- [ ] Audit and emergency stop disabling remain denied.
- [ ] CLI, MCP, SDK adapter, and host paths preserve `ControlPlane`.

## Human Approval

- [ ] Human reviewer approves release branch.
- [ ] GitHub Pages settings decision is recorded.
- [ ] Public repository URL/badge decision is recorded.
- [ ] Wheel/sdist build dependency decision is recorded if still deferred.
- [ ] Lint/type dependency decisions are recorded if still deferred.
- [ ] Rollback plan is understood.
