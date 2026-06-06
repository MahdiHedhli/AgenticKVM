# Linting

AgenticKVM currently uses a dependency-free lint sanity gate instead of adopting
a full lint toolchain.

## Command

```bash
python scripts/lint-sanity.py
```

The script checks:

- Python files in `src/`, `tests/`, and `scripts/` parse with `ast`
- no `pdb.set_trace`, interactive breakpoint calls, or explicit debug-only
  markers are present
- example and site files do not contain obvious raw secret-like keys
- example and site URLs remain documentation-safe
- public docs and site files avoid forbidden live-support overclaims
- mainline package metadata does not include the trial-only MCP SDK dependency

## Non-Goals

The script does not replace a formatter or a full static-analysis stack. Future
work may add Ruff, mypy, pyright, or another tool after a dependency and
workflow review.

## CI Policy

The lint sanity gate is safe for CI because it:

- uses only the Python standard library
- does not open network connections
- does not read secrets
- does not resolve credential references
- does not inspect live provider targets
- does not require the SDK trial dependency

## Future Decisions

Before adding a full lint dependency, decide:

- whether the project wants formatting enforcement
- which Python versions the tool must support
- whether CI should fail on style, import order, or only safety-oriented checks
- how to keep generated or ignored files out of lint scope
