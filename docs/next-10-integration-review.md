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
| 7. Local operator console | Complete; local JSON CLI status console added |
| 8. Production audit backend v1 | Complete; explicit-path SQLite audit backend v1 added |
| 9. PiKVM input-control phase | Fake-only/gated scaffold only; no live input |
| 10. Recovery playbooks | Complete; mock-safe playbook framework added |

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

## Move 7: Local Operator Console

Status: complete.

Implemented:

- `agentickvm status`
- `agentickvm console`
- provider and target summaries from the configured registries
- active policy mode summary
- pending approval summaries when `--approval-path` is supplied
- audit hash-chain verification when `--audit-path` is supplied
- explicit safety fields showing no listener and no live-provider default

Safety properties:

- read-only
- no provider execution
- no credential resolution
- no environment secret reads
- no network listener
- no auto-approval

## Move 8: Production Audit Backend V1

Status: complete.

Implemented:

- `SQLiteAuditSink`
- SQLite hash-chain verification
- recent event listing
- explicit-path JSON export
- CLI commands:
  - `agentickvm audit verify --sqlite-path <path>`
  - `agentickvm audit list --sqlite-path <path>`
  - `agentickvm audit export --sqlite-path <path> --output <path>`
- runtime opt-in through `--audit-sqlite-path`
- tests for persistence, verification, tamper detection, export safety, CLI
  audit commands, and console reporting

Safety properties:

- standard library only
- explicit paths only
- tests use temp directories only
- no network
- no credentials
- no provider execution path changes
- JSONL audit remains supported

## Move 10: Safe Recovery Playbooks

Status: complete.

Implemented:

- playbook model
- playbook registry
- playbook runner
- dry-run support
- CLI commands:
  - `agentickvm playbooks list`
  - `agentickvm playbooks dry-run <name> --target <target>`
  - `agentickvm playbooks run <name> --target <target>`
- initial playbooks:
  - `observe-target-health`
  - `capture-screen-evidence`
  - `inspect-boot-status`
  - `collect-pre-recovery-evidence`
  - `wait-for-login-prompt`
- tests for dry-run, mock execution, unknown target fail-closed behavior,
  audit path use, and provider-bypass prevention

Safety properties:

- executes through `MCPRouter` and `ControlPlane`
- stops on non-`ok` step results
- no direct provider calls
- no live providers by default
- no credential resolution
- no mutating real-provider behavior
