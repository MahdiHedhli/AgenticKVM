# Next-10 Integration Review

Branch: `feature/agentickvm-next-10-integration`

Base branch: `feature/package-release-hardening`

Base commit: `20a764c`

## Purpose

This branch coordinates the next ten strategic moves while preserving the
release-quality, GitHub Pages, and package hardening gates already added on the
mainline feature path.

The branch is not a live provider branch, not an SDK trial merge, and not a
main merge branch.

## Move 1: Release-Quality And GitHub Pages Integration

Status: complete.

Checks performed:

- `feature/github-pages-site` is an ancestor of
  `feature/package-release-hardening`
- `feature/release-quality-gates` is an ancestor of
  `feature/package-release-hardening`
- `site/index.html` exists
- `.github/workflows/pages.yml` exists
- `.github/workflows/ci.yml` exists
- release-quality scripts exist
- package-release hardening scripts exist

No merge was needed because `feature/package-release-hardening` already
contains the GitHub Pages site, Pages workflow, CI workflow, release quality
gates, package hardening scripts, release docs, and safety tests.

## Release Gates Confirmed At Branch Start

The branch baseline passed:

- `python3 scripts/check-package.py`
- `python3 scripts/build-package.py`
- `python3 scripts/smoke-cli.py`
- `python3 scripts/lint-sanity.py`
- `python3 scripts/type-sanity.py`
- `python3 scripts/validate-docs.py`
- `python3 scripts/check-site.py`
- `python3 scripts/generate-release-manifest.py --output <temp path>`
- `uv run --offline --with pytest --python python3.13 python -m pytest`

Pytest result: 537 passed.

## SDK Trial Boundary

The SDK trial branch remains separate:

- branch: `trial/mock-only-mcp-python-sdk`
- trial dependency: `mcp==1.27.2`
- trial status: continue trial, not selected for mainline adoption

This integration branch does not merge the SDK trial branch and does not add
the `mcp` dependency.

## Safety Boundary

This branch must not:

- touch real hardware
- run live provider smoke tests
- use credentials
- resolve credential refs in tests
- enable real providers by default
- enable live MCP server behavior by default
- bypass `ControlPlane`
- bypass provider or target registries
- bypass audit
- auto-approve

Automated tests remain mock-only, fixture-only, temp-path-only, and safe.

## Move Status Summary

| Move | Status |
| --- | --- |
| 1. Release-quality/GitHub Pages merge | Complete; already integrated through base branch |
| 2. Python MCP SDK trial review | Complete; continue trial, hold mainline adoption |
| 3. Mock-only MCP stdio mainline | Deferred; no SDK dependency or code port on this branch |
| 4. Operator approval transport | Complete; local explicit-path queue and CLI commands added |
| 5. PiKVM observe-only | Disabled-by-default docs/spec/tests only unless safely bounded |
| 6. Redfish observe-only | Disabled-by-default docs/spec/tests only unless safely bounded |
| 7. Local operator console | Candidate for local CLI/status implementation |
| 8. Production audit backend v1 | Candidate for local SQLite/file-backed implementation |
| 9. PiKVM input-control phase | Fake-only/gated scaffold only; no live input |
| 10. Recovery playbooks | Candidate for mock/fake dry-run framework |

## Next Gate

Proceed to local console, audit, or playbook work that remains dependency-free
and mock-only. SDK adoption requires a separate human-reviewed branch.

## Move 4: Local Operator Approval Transport

Status: complete.

Implemented:

- path-scoped `LocalApprovalQueue`
- persisted local approval records with pending, approved, denied, expired, and
  consumed states
- one-time and session approval scopes
- exact binding to session, target, provider, capability, params fingerprint,
  expiry, and operator id
- CLI commands:
  - `agentickvm --approval-path <path> approvals list`
  - `agentickvm --approval-path <path> approvals show <id>`
  - `agentickvm --approval-path <path> approvals approve <id>`
  - `agentickvm --approval-path <path> approvals deny <id>`
  - `agentickvm --approval-path <path> approvals expire <id>`
- optional `--audit-path` support using the existing local JSONL audit sink
- tests for one-time consumption, session reuse, denial, expiry, audit chain
  verification, and redaction

Safety properties:

- disabled unless an explicit `--approval-path` is supplied
- approval submission does not execute providers
- approved resumption still goes through `MCPRouter`, registries, policy,
  audit, and `ControlPlane`
- no auto-approval
- no credential resolution
- tests use temp directories only
