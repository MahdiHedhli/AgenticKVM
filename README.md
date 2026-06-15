# AgenticKVM

Give your AI agent hands for real machines, with safety guardrails built in.

AgenticKVM is a policy-controlled infrastructure control plane for AI-assisted
machine observation, recovery, and operation. It is designed to route every
agent or tool action through target/provider registries, capability mapping,
policy decisions, operator approvals, and audit before any provider adapter can
execute.

This repository is the canonical AgenticKVM implementation. The older
`Agentic-KVM` repository is a donor spike and dogfood prototype used for lessons
only.

## Public Beta Status

AgenticKVM has a public pre-release for review, but the product launch gate is
now the real killer demo: an agent recovering a wedged machine through the full
Agentic Control Tower (ACT) clearance chain. The project is moving from
public-beta preparation into control-plane-to-tower work, trusted operator
channels, and live out-of-band recovery slices.

AgenticKVM is out-of-band only. Active scope is KVM, BMC, PiKVM, Redfish, iLO,
iDRAC, IPMI / Supermicro BMC, policy, approvals, audit, provider registries,
and target registries. In-band remote desktop/session providers are parked and
are not on the AgenticKVM roadmap.

The existing site, release-quality gates, and beta docs remain useful
preparation, but public beta is deferred until the killer demo exists. Mocks
talking to mocks are not the launch criterion.

Real hardware providers are intentionally not enabled by default.

- safe mock and fixture workflows are implemented
- policy, approval, audit, provider, target, CLI, MCP scaffold, and release
  gates are present
- local SQLite audit backend v1 and local approval queue are available for
  review and testing
- live provider execution is still gated and disabled
- live MCP server adoption is deferred
- the Python MCP SDK trial remains isolated on a separate branch and is not a
  mainline dependency

Do not use this beta for unattended production hardware recovery, live PiKVM
input, live Redfish mutation, credential handling, or live provider smoke unless
a separate operator-approved plan explicitly allows it.

## What Works Today

### Control Plane

- constitution-backed safety rules
- capability registry
- provider registry
- target registry
- policy decisions:
  - `deny`
  - `ask_each_time`
  - `ask_once_per_session`
  - `allow`
  - `allow_with_limits`
- fail-closed behavior for unknown capabilities, providers, targets, and tools
- hard invariants that block policy modification, audit disabling, emergency
  stop disabling, and raw secret reveal by default

### Providers

- mock provider for offline tests
- PiKVM fixture observe path
- Redfish fixture/readiness docs and fake paths
- disabled placeholder configs for future live providers
- live-provider preflight gates for future PiKVM/Redfish work

Live PiKVM and Redfish network execution are not enabled in this beta.

### CLI

The CLI supports safe mock/fixture workflows:

- list providers
- list targets
- call mock observe and power-state tools
- call PiKVM fixture observe tools
- receive `approval_required`
- receive `denied`
- fail closed on unknown tools, unknown targets, and disabled providers
- run local approval queue commands
- run local audit commands
- run safe recovery playbooks
- show local operator status/console output

### Operator Approval

- local explicit-path approval queue
- pending, approved, denied, expired, and consumed states
- one-time approval consumption
- session-scoped approval behavior
- parameter fingerprint matching
- redacted operator previews
- audit events for approval lifecycle

### Audit

- local JSONL audit sink
- local SQLite audit backend v1
- explicit audit path requirements
- redaction before persistence
- hash-chain verification
- checkpoint helpers
- export helpers
- event listing and inspection
- tamper/deletion detection tests

The SQLite backend is local and explicit-path only. External audit backends,
SIEM integration, managed retention, and checkpoint signing remain future work.

### MCP And Agents

- dependency-free MCP-style models
- MCP router
- mock-only MCP SDK adapter scaffold
- mock-only host compatibility layer
- host conformance fixtures for approval, audit, artifacts, provider errors,
  and JSON-safe result shapes

The live MCP server is not adopted in mainline. The Python MCP SDK trial remains
on `trial/mock-only-mcp-python-sdk`.

### Recovery Playbooks

Safe playbook framework with:

- playbook registry
- dry-run support
- mock/fake execution only
- required capability mapping
- risk tier metadata
- approval checkpoints
- audit for steps
- fail-closed behavior for unsupported capabilities

Current playbooks are evidence-gathering and mock-safe, not live recovery
automation.

### Website And Release Gates

- static GitHub Pages-ready site under `site/`
- GitHub Pages workflow that publishes only `site/`
- public site at `https://mahdihedhli.github.io/AgenticKVM/`
- mock-only CI
- package metadata checks
- package artifact readiness checks
- CLI smoke matrix
- lint sanity
- type sanity
- docs/spec validation
- site safety checks
- public beta readiness check
- release manifest generator

GitHub Pages is enabled for GitHub Actions and publishes the static `site/`
directory.

## Install From Source

Requirements:

- Python 3.11 or newer
- Git
- `uv` recommended for the same workflow used by the project

Clone the repository:

```bash
git clone https://github.com/MahdiHedhli/AgenticKVM.git
cd AgenticKVM
```

Recommended `uv` workflow:

```bash
uv venv --python python3.13 .venv
uv pip install --python .venv/bin/python -e .
source .venv/bin/activate
```

Then verify the CLI:

```bash
agentickvm --help
agentickvm list-providers
agentickvm list-targets
```

Standard `venv` also works on Python installations with `ensurepip` available:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

If you do not want to install the package yet, use the source-tree module path:

```bash
PYTHONPATH=src python3 -m agentickvm.cli.main --help
PYTHONPATH=src python3 -m agentickvm.cli.main list-providers
```

## Safe Local Smoke Tests

Run the same broad validation matrix used for the public beta candidate:

```bash
python3 scripts/check-package.py
python3 scripts/build-package.py
python3 scripts/smoke-cli.py
python3 scripts/lint-sanity.py
python3 scripts/type-sanity.py
python3 scripts/validate-docs.py
python3 scripts/check-site.py
python3 scripts/generate-release-manifest.py --output /tmp/agentickvm-release-manifest.json
python3 scripts/check-public-beta.py
uv run --offline --with pytest --python python3.13 python -m pytest
```

Expected beta result at the current merge point:

- local script matrix passes
- package build check may report documented `deferred` status if optional build
  tooling is unavailable
- pytest passes with the current mock-only suite

No test should require real hardware, live provider network calls, credentials,
external services, remote desktop software, a production audit store, or a live
MCP host.

## CLI Examples

List configured providers and targets:

```bash
agentickvm list-providers
agentickvm list-targets
```

Call safe mock tools:

```bash
agentickvm call --target mock-host --tool observe_screen
agentickvm call --target mock-host --tool get_power_state
```

Use the PiKVM fixture observe path:

```bash
agentickvm \
  --config examples/config/pikvm-observe-fixture.yaml \
  call \
  --target pikvm-fixture-target \
  --provider pikvm-fixture \
  --tool observe_screen
```

Create an approval request for a gated mock action:

```bash
agentickvm \
  --approval-path /tmp/agentickvm-approvals.json \
  call \
  --target mock-host \
  --tool force_restart
```

Inspect local operator status:

```bash
agentickvm status
agentickvm console
```

Run playbook dry-runs:

```bash
agentickvm playbooks list
agentickvm playbooks dry-run observe-target-health --target mock-host
```

Use SQLite audit locally with an explicit temp path:

```bash
agentickvm \
  --audit-sqlite-path /tmp/agentickvm-audit.sqlite \
  call \
  --target mock-host \
  --tool get_power_state

agentickvm audit verify --sqlite-path /tmp/agentickvm-audit.sqlite
agentickvm audit list --sqlite-path /tmp/agentickvm-audit.sqlite
```

## What Is Left

The next major gates are intentionally explicit:

- enable GitHub Pages settings after maintainer review
- decide the first pre-release tag format
- decide when to bump package metadata from `0.0.0`
- decide whether wheel/sdist build tooling should become mandatory
- select full lint, type, and coverage tooling
- review the Python MCP SDK trial before any mainline adoption
- plan live PiKVM observe-only implementation
- plan live Redfish GET-only observe implementation
- select a credential strategy for future live providers
- mature the approval UX beyond local file-backed queues
- mature audit beyond local SQLite
- define external audit/export retention policy
- design manual lab-only live smoke procedures

Still deferred:

- live PiKVM execution
- live Redfish execution
- PiKVM keyboard, mouse, paste, or hotkey input
- Redfish reset, boot override, virtual media, BIOS, firmware, storage,
  network, or account mutation
- live MCP server
- Python MCP SDK mainline dependency
- RustDesk, VNC, RDP, MeshCentral, BrowserBridge, and desktop/session providers
- external production audit backend
- unattended production hardware recovery

## What We Need From Beta Testers

Helpful beta feedback is concrete, reproducible, and safety-aware.

Please test:

- install from a clean clone
- all scripts in the safe local smoke matrix
- CLI provider and target listing
- mock observe and power-state calls
- PiKVM fixture observe call
- approval queue creation, approve, deny, expire, and consume flows
- JSONL and SQLite audit verify/list/export/checkpoint flows
- safe playbook dry-runs and mock runs
- static site readability and broken links
- docs clarity for safety boundaries
- GitHub Actions CI behavior on forks or PRs

Please report:

- operating system
- Python version
- whether you used `uv`, `pip`, or another workflow
- exact command run
- expected result
- actual result
- redacted logs or tracebacks
- whether any behavior could confuse users into thinking live providers are
  enabled
- whether any output appears to expose secrets, hostnames, IP addresses, raw
  screenshots, audit databases, approval queues, or generated artifacts

Please do not include:

- credentials
- API keys
- tokens
- cookies
- real hostnames
- real IP addresses
- screenshots of sensitive systems
- raw audit databases
- generated manifests from private environments
- approval queue files from real operations

Use the issue templates in `.github/ISSUE_TEMPLATE/` and follow `SECURITY.md`
for vulnerability reports.

## Documentation Map

- [Constitution](.specify/memory/constitution.md)
- [Control-plane spec](specs/002-control-plane/)
- [Security model](docs/security-model.md)
- [Control plane](docs/control-plane.md)
- [Operator approval](docs/operator-approval.md)
- [ACT clearance client](docs/act-clearance-client.md)
- [Approval notifiers](docs/approval-notifiers.md)
- [Approval Broker v1 review](docs/approval-broker-v1-review.md)
- [MCP elicitation](docs/mcp-elicitation.md)
- [Host conformance matrix](docs/conformance-matrix.md)
- [Provider contracts](docs/provider-contracts.md)
- [Provider taxonomy](docs/provider-taxonomy.md)
- [Roadmap](docs/roadmap.md)
- [Parking lot: in-band remote session providers](docs/parking-lot/inband-remote-session-providers.md)
- [Development guide](docs/development.md)
- [Testing guide](docs/testing.md)
- [Packaging notes](docs/packaging.md)
- [CLI smoke matrix](docs/cli-smoke.md)
- [Linting](docs/linting.md)
- [Type checking](docs/type-checking.md)
- [Coverage policy](docs/coverage-policy.md)
- [Release readiness](docs/release-readiness.md)
- [Release artifacts](docs/release-artifacts.md)
- [Public beta readiness](docs/public-beta-readiness.md)
- [Public beta cutover plan](docs/public-beta-cutover-plan.md)
- [Public beta final review](docs/public-beta-final-review.md)
- [Public beta merge commands](docs/public-beta-merge-commands.md)
- [Public beta tagging plan](docs/public-beta-tagging-plan.md)
- [Public beta final handoff](docs/public-beta-final-handoff.md)
- [Public beta release notes](docs/releases/public-beta-0.1.0.md)
- [Public beta known limitations](docs/public-beta-known-limitations.md)
- [Public beta security statement](docs/public-beta-security-statement.md)
- [Public beta risk register](docs/public-beta-risk-register.md)
- [Live provider preflight](docs/live-provider-preflight.md)
- [Maintainer runbook](docs/maintainer-runbook.md)
- [GitHub Pages setup](docs/github-pages.md)

## Repository Map

- `.specify/memory/constitution.md`: non-negotiable project principles
- `specs/002-control-plane/`: control-plane source-of-truth spec and contracts
- `docs/`: architecture, security, release, roadmap, and beta documentation
- `site/`: static GitHub Pages-ready public site
- `examples/`: safe mock and disabled-placeholder configuration examples
- `src/agentickvm/`: Python package source
- `tests/`: mock-only unit, contract, and security tests
- `scripts/`: local validation and release-readiness helpers
- `.github/workflows/`: mock-only CI and static Pages workflows

## Core Architecture Rule

No MCP tool, CLI command, API handler, or agent workflow may call a provider
directly. Every action must flow through:

1. agent/tool request
2. capability request
3. policy decision
4. ACT clearance if required
5. provider adapter
6. structured audit event
7. result

Provider adapters execute already-authorized requests. They do not own policy
and must not silently widen scope.

## Control Modes

Visible operator modes:

- Observe
- Assisted
- Supervised
- Full Control
- Custom

Internal policy decisions:

- deny
- ask_each_time
- ask_once_per_session
- allow
- allow_with_limits

Unknown capabilities default to `deny`.

## Source Of Truth

AgenticKVM is spec-driven. The source-of-truth order is:

1. `.specify/memory/constitution.md`
2. `specs/*/spec.md`
3. `specs/*/contracts/*`
4. `docs/*`
5. implementation and tests

When code and specs disagree, update the specification first or stop.

## Repository Map

- `.specify/memory/constitution.md`: non-negotiable project principles
- `specs/001-product-vision/`: product mission, plan, and bootstrap tasks
- `specs/002-control-plane/`: control-plane behavior, contracts, data model,
  research notes, and quickstart
- `docs/`: architecture, security model, provider contracts, migration plan,
  roadmap, heartbeat, release readiness, and threat model
- `site/`: static GitHub Pages-ready marketing/docs site
- `examples/policies/`: starter mode policies
- `src/agentickvm/`: minimal Python package scaffold
- `tests/`: unit, contract, and security tests
- `scripts/`: local package and docs validation helpers
- `.github/workflows/`: mock-only CI and static GitHub Pages workflows

## Website

This branch includes a static GitHub Pages-ready site under `site/`.

The site is plain HTML/CSS with no JavaScript, tracking, remote fonts, live
provider behavior, credentials, or MCP SDK dependency. It presents
AgenticKVM's safety-first architecture and roadmap while keeping public beta,
live providers, and live MCP server work explicitly gated.

GitHub Pages setup notes are in `docs/github-pages.md`.

## Development

Use the [development guide](docs/development.md) and
[testing guide](docs/testing.md) for contributor workflow details.

Preferred local test command:

```bash
uv run --offline --with pytest --python python3.13 python -m pytest
```

Release-quality validation helpers:

```bash
python scripts/check-package.py
python scripts/build-package.py
python scripts/smoke-cli.py
python scripts/lint-sanity.py
python scripts/type-sanity.py
python scripts/validate-docs.py
python scripts/check-site.py
python scripts/generate-release-manifest.py --output /tmp/agentickvm-release-manifest.json
python scripts/check-public-beta.py
```

The test suite must use mocks and schemas only. Real hardware is never used in
CI.

Workflow badges are intentionally not added until the public repository URL is
confirmed.

## License

MIT. See `LICENSE`.
