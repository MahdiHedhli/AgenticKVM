# Coverage Policy

AgenticKVM treats coverage as a release-risk signal, not a vanity percentage.
The current branch does not add a coverage dependency. Percentage enforcement is
deferred until a tool such as `coverage.py` is reviewed and accepted.

## Critical Coverage Areas

Release candidates should keep focused coverage over:

- control plane request handling
- policy engine decisions
- capability registry
- provider registry
- target registry
- config loader and config safety checks
- MCP router
- MCP SDK adapter scaffold
- MCP host compatibility layer
- approval lifecycle
- audit JSONL persistence
- audit checkpoint/export/retention helpers
- provider error taxonomy
- mock provider behavior
- fake PiKVM and Redfish observe paths
- CLI mock and fixture paths
- end-to-end process/routine suite (observe, mock-cleared actuation, redaction,
  fail-closed, and selectable auth-channel routing)
- real ACT clearance proof verification against the committed tower vector
- workflow safety checks
- docs/spec/site safety checks
- release safety regressions

## Required Qualitative Gates

Before release, tests must prove:

- unknown capability/provider/target fail closed
- disabled provider/target fail closed
- hard invariants remain denied
- approval-required flows remain first-class
- audit events are emitted and redacted
- audit checkpoint/export verification detects tampering
- live provider placeholders cannot execute
- live provider configs are rejected by default
- CLI/MCP/host paths preserve `ControlPlane`
- mock-cleared actuation runs only on fixtures and never claims a hardware action
- the selected auth channel routes the clearance step and surfaces its warning
- public site/docs avoid live-support overclaims
- CI and Pages workflows do not require secrets or live provider targets

## Future Percentage Gate

When a coverage tool is adopted, define:

- line coverage threshold
- branch coverage threshold if supported
- files or paths excluded from percentage calculation
- minimum coverage for control-plane/security-critical modules
- report artifact path
- CI failure behavior

Suggested initial threshold after tool adoption:

- overall line coverage: measured first, then set a conservative floor
- control-plane/security-critical modules: stricter floor after baseline report

Do not set arbitrary thresholds before measuring the current codebase.

## Exclusions

Potential exclusions must be explicit and reviewed:

- generated files
- test fixtures
- static site assets
- docs-only files
- optional future live smoke harnesses outside CI

Exclusions must not hide untested policy, approval, audit, registry, provider,
or MCP routing behavior.

## Current Status

Current release hardening relies on:

- `python scripts/check-package.py`
- `python scripts/build-package.py`
- `python scripts/smoke-cli.py`
- `python scripts/lint-sanity.py`
- `python scripts/type-sanity.py`
- `python scripts/validate-docs.py`
- `uv run --offline --with pytest --python python3.13 python -m pytest`

Coverage percentage reporting is deferred.
