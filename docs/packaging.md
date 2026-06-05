# Packaging

## Current Package Shape

AgenticKVM is a Python package using a `src/` layout and setuptools:

- package name: `agentickvm`
- build backend: `setuptools.build_meta`
- package discovery: `src`
- CLI entry point: `agentickvm = agentickvm.cli:main`

The package currently has no runtime dependencies in `pyproject.toml`.

The trial-only Python MCP SDK dependency (`mcp==1.27.2`) must not appear on
mainline or release-quality branches unless separately approved.

## Current Verification

Run:

```bash
python scripts/check-package.py
```

The script verifies:

- required project metadata
- `src` package discovery
- CLI entry-point declaration
- package import
- CLI import
- absence of the trial MCP SDK dependency
- no accidental `python -m agentickvm` behavior

## Build Artifact Status

This branch does not add wheel or source distribution build tooling. The local
quality gate is metadata/import verification.

Future build verification may add a reviewed build command such as:

```bash
python -m build
```

Only add that command after deciding whether to add or vendor build tooling,
and after confirming it does not introduce unnecessary dependency churn.

## Inclusion Notes

Setuptools package discovery points at `src`, so documentation, tests, specs,
and `site/` are not Python packages. Future release packaging should explicitly
decide whether source distributions include docs/specs/site artifacts.
