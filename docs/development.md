# Development Guide

This guide covers day-to-day development for AgenticKVM contributors.

AgenticKVM is a spec-driven control plane. The implementation must stay aligned
with the constitution, control-plane contracts, provider registry, target
registry, approval flow, and audit flow.

## Authority Order

Use this order when a change touches behavior:

1. `.specify/memory/constitution.md`
2. `specs/*/spec.md`
3. `specs/*/contracts/*`
4. `docs/*`
5. `src/agentickvm/*`
6. `tests/*`

If code and specs disagree, update the spec first or stop and ask for review.

## Local Setup

AgenticKVM currently has a small Python package with no mainline runtime
dependencies beyond the standard packaging backend. Tests are run with `pytest`.

Preferred local test command:

```bash
uv run --offline --with pytest --python python3.13 python -m pytest
```

If the offline cache is unavailable, use the existing safe test command for the
branch and note the fallback in your handoff.

## Branch Model

- Work on a feature branch, not directly on `main`.
- Keep the SDK trial branch separate from mainline branches.
- Do not merge `trial/mock-only-mcp-python-sdk` unless a later human-reviewed
  adoption decision explicitly allows it.
- Do not add the trial-only `mcp==1.27.2` dependency to mainline branches.

## Change Shape

Prefer bounded changes that include:

- spec or docs update when behavior changes
- focused implementation
- mock-only tests
- security or audit consideration
- roadmap or heartbeat update for larger maturity lanes

Avoid broad refactors unless they are required to preserve a contract.

## Provider Development Rules

Provider adapters execute already-authorized requests. They do not own policy.

Every external interface must route through:

1. MCP, CLI, host adapter, or future API boundary
2. provider and target registries
3. capability request
4. policy decision
5. approval flow if required
6. `ControlPlane`
7. provider adapter
8. audit event
9. structured result

Do not let tools, CLI commands, MCP handlers, host adapters, or future SDK
server handlers call providers directly.

## Adding Capabilities

When adding a capability:

- define the capability in the capability registry
- assign risk and family metadata
- update policy rules and expected mode behavior
- update MCP/CLI mapping only if the capability should be exposed
- add deny/approval/allow tests for relevant modes
- add audit expectations
- update docs and specs

Unknown capabilities must continue to fail closed.

## Adding Providers

Provider work must start mock-first or fixture-first.

Before any live provider work:

- provider-specific spec exists
- allowed and disallowed capabilities are explicit
- config contract rejects raw secrets
- provider is disabled by default
- no live network calls run in tests
- no real hardware is used in CI
- audit behavior is covered
- approval gates are covered
- manual smoke plan exists

Live provider behavior requires a separate operator-approved gate.

## Configuration Rules

- Commit only safe example config.
- Do not commit secrets, tokens, cookies, passwords, private keys, or raw
  credential material.
- Credential references may be documented, but tests must not resolve them.
- Real provider configs must remain disabled by default.
- Fixture mode must be explicit and distinguishable from live mode.

## Website And Docs

The static site under `site/` is plain HTML/CSS. It must not include analytics,
tracking, remote fonts, secrets, live provider config, or SDK trial dependency
references as mainline behavior.

Public docs and site copy must not overclaim live provider support.

## Handoff Expectations

For substantial lanes, include:

- branch and starting commit
- commits created
- files changed
- tests run
- final result
- security notes
- blockers and deferred unsafe tasks
- next recommended task
