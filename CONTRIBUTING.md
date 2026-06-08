# Contributing To AgenticKVM

AgenticKVM is spec-driven. Contributions should start with the constitution,
specification, and contracts before implementation.

## Ground Rules

- Do not add implementation behavior that contradicts `.specify/memory/constitution.md`.
- Do not let MCP tools, CLI commands, API handlers, or workflows call providers
  directly.
- Do not implement real hardware behavior without a matching spec, contract,
  mock, tests, audit path, and safety review.
- Do not use real hardware in CI.
- Do not introduce provider-owned policy decisions.
- Do not weaken audit, approval, emergency stop, or scope controls.

## Preferred Change Shape

Small verified slices beat broad unsafe automation. A good change usually
contains:

- spec or contract update
- focused implementation
- mock-based tests
- audit/security consideration
- documentation update when behavior changes

## Development

Use the detailed local workflow in `docs/development.md` and the test matrix in
`docs/testing.md`.

Preferred test command:

```bash
uv run --offline --with pytest --python python3.13 python -m pytest
```

If the offline cache is unavailable, use the safest existing test command and
record that fallback in your handoff.

Real provider tests must be explicitly separated from CI, opt-in only,
operator-approved, and guarded by target scope declarations. They must not read
secrets from the environment in the main test suite.

## Provider Contributions

Provider work starts mock-first or fixture-first. Before any live provider work,
the provider needs a spec, config contract, redaction behavior, audit coverage,
approval gates, disabled-by-default config, and manual smoke plan.

Provider adapters must execute already-authorized requests only. They must not
make policy decisions, silently expand scope, or bypass `ControlPlane`.

## Review Checklist

Before proposing a change, check:

- policy boundary remains central
- unknown capabilities still deny
- unknown providers and targets still fail closed
- dangerous actions have explicit scope
- approval prompts are explainable
- audit events are structured and mandatory
- secrets are redacted by default
- provider adapters remain policy-free
- CI remains mock-only and does not require secrets
- the SDK trial dependency has not been added to mainline branches
