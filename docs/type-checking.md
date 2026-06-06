# Type Checking

AgenticKVM currently uses a dependency-free type sanity gate. Full static type
checking with mypy, pyright, or another tool remains a future dependency and CI
decision.

## Command

```bash
python scripts/type-sanity.py
```

The script checks:

- key modules import without circular import failures
- public request/result dataclasses have field annotations
- MCP, host, and provider result models serialize to JSON-safe dictionaries
- sample secret-shaped values are redacted before JSON output
- mainline package metadata does not include the trial-only MCP SDK dependency
- the trial SDK package is not imported by the sanity path

## Current Coverage

The sanity gate covers public contracts around:

- `ControlPlane`
- MCP router models
- MCP SDK adapter scaffold models
- MCP host compatibility models
- provider action request/result/status models

## Non-Goals

This gate does not prove full static type correctness. It does not replace:

- mypy
- pyright
- Ruff type-aware rules
- IDE/static analyzer review

## Future Decision

Before adopting a full type checker, decide:

- tool choice
- Python version target
- strictness level
- how generated or fixture files are handled
- whether CI should fail on all type issues or only contract-critical modules
- whether type-check dependencies should be pinned or constrained
