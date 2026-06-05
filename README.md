# AgenticKVM

Spec-driven control plane for safe agentic out-of-band infrastructure operations.

AgenticKVM provides safe agentic control for real machines by routing every action
through a policy-governed control plane before any provider adapter can touch an
out-of-band interface.

This repository is the canonical AgenticKVM implementation. The older
`Agentic-KVM` repository is a donor spike and dogfood prototype used for lessons,
not an authoritative source for architecture or implementation.

## Status

AgenticKVM is in bootstrap. The current repository establishes the constitution,
product vision, control-plane specification, contracts, security model, migration
plan, mock provider scaffold, and initial safety tests.

Real hardware providers are intentionally not implemented yet.

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
  roadmap, heartbeat, and threat model
- `site/`: static GitHub Pages-ready marketing/docs site
- `examples/policies/`: starter mode policies
- `src/agentickvm/`: minimal Python package scaffold
- `tests/`: unit, contract, and security tests

## Website

This branch includes a static GitHub Pages-ready site under `site/`.

The site is plain HTML/CSS with no JavaScript, tracking, remote fonts, live
provider behavior, credentials, or MCP SDK dependency. It presents
AgenticKVM's safety-first architecture and roadmap while keeping live providers
and live MCP server work explicitly gated.

GitHub Pages setup notes are in `docs/github-pages.md`.

## Development

Install test dependencies in your preferred Python environment, then run:

```bash
PYTHONPATH=src python3 -m pytest
```

The test suite must use mocks and schemas only. Real hardware is never used in
CI.

## License

MIT. See `LICENSE`.
