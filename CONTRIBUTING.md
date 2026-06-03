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

Run tests with:

```bash
PYTHONPATH=src python3 -m pytest
```

Real provider tests must be explicitly separated from CI, opt-in only, and
guarded by environment variables and target scope declarations.

## Review Checklist

Before proposing a change, check:

- policy boundary remains central
- unknown capabilities still deny
- dangerous actions have explicit scope
- approval prompts are explainable
- audit events are structured and mandatory
- secrets are redacted by default
- provider adapters remain policy-free
