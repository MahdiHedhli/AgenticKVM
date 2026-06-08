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
python scripts/build-package.py
```

`scripts/check-package.py` verifies:

- required project metadata
- `src` package discovery
- CLI entry-point declaration
- package import
- CLI import
- absence of the trial MCP SDK dependency
- no accidental `python -m agentickvm` behavior

`scripts/build-package.py` verifies package artifact readiness without adding
new dependencies:

- project name and version
- CLI script metadata
- no trial-only `mcp==1.27.2` dependency
- package metadata does not claim live provider support
- live providers are reported disabled
- artifact build status is JSON-safe

If the optional `build` module is available, the script builds a wheel and
source distribution in a temporary directory, validates artifact names and
contents, and verifies importability from the wheel.

If the optional `build` module is unavailable, the script reports:

```json
{
  "status": "deferred",
  "reason": "python build module is not installed"
}
```

That deferred status is allowed for the current release-quality branch because
adding build tooling is a separate dependency decision.

## Build Artifact Status

This branch does not add wheel or source distribution build tooling. The local
quality gate now includes metadata/import verification plus artifact-readiness
verification that builds only when existing tooling is available.

Future build verification may add a reviewed build command such as:

```bash
python -m build
```

Only add that command after deciding whether to add or vendor build tooling,
and after confirming it does not introduce unnecessary dependency churn.

To require artifact builds once tooling is approved, run:

```bash
python scripts/build-package.py --require-build
```

## Inclusion Notes

Setuptools package discovery points at `src`, so documentation, tests, specs,
and `site/` are not Python packages. Future release packaging should explicitly
decide whether source distributions include docs/specs/site artifacts.
