# AgenticKVM

Spec-driven control plane for safe agentic out-of-band infrastructure operations.

AgenticKVM provides safe agentic control for real machines by routing every action
through a policy-governed control plane before any provider adapter can touch an
out-of-band interface.

This repository is the canonical AgenticKVM implementation. The older
`Agentic-KVM` repository is a donor spike and dogfood prototype used for lessons,
not an authoritative source for architecture or implementation.

## Status

AgenticKVM is moving from public-beta preparation into the real out-of-band
control-plane work: Approval Broker v1, signed grants, trusted operator
approval channels, and the path to a killer demo where an agent recovers a real
wedged machine through the full approval chain.

AgenticKVM is out-of-band only. Active scope is KVM, BMC, PiKVM, Redfish, iLO,
iDRAC, IPMI / Supermicro BMC, policy, approvals, audit, provider registries,
and target registries. In-band remote desktop/session providers are parked and
are not on the AgenticKVM roadmap.

Public beta is deferred until after the killer demo. The existing site, release
quality gates, and beta docs remain useful preparation, but mocks talking to
mocks are not the launch criterion.

Real hardware providers are intentionally not enabled by default.

The Python MCP SDK dependency trial remains isolated on a separate trial branch
and is not part of mainline metadata.

## Quick Links

- [Security model](docs/security-model.md)
- [Control plane](docs/control-plane.md)
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

## Core Architecture Rule

No MCP tool, CLI command, API handler, or agent workflow may call a provider
directly. Every action must flow through:

1. agent/tool request
2. capability request
3. policy decision
4. operator approval if required
5. provider adapter
6. structured audit event
7. result

Provider adapters execute already-authorized requests. They do not own policy and
must not silently widen scope.

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
