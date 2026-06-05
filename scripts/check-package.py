#!/usr/bin/env python3
"""Validate package metadata and import readiness.

This script is dependency-free and safe for local and CI use. It does not build
artifacts, contact package indexes, or import live providers.
"""

from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class CheckFailure(RuntimeError):
    """Raised when package metadata does not meet release-gate expectations."""


def main() -> int:
    try:
        payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
        _check_project_metadata(payload)
        _check_imports()
    except Exception as exc:
        print(f"package check failed: {exc}", file=sys.stderr)
        return 1
    print("package check passed")
    return 0


def _check_project_metadata(payload: dict) -> None:
    project = payload.get("project")
    if not isinstance(project, dict):
        raise CheckFailure("missing [project] metadata")
    if project.get("name") != "agentickvm":
        raise CheckFailure("project name must be agentickvm")
    if not isinstance(project.get("version"), str) or not project["version"]:
        raise CheckFailure("project version is required")
    if project.get("requires-python") != ">=3.11":
        raise CheckFailure("requires-python must remain >=3.11")
    dependencies = project.get("dependencies", [])
    if dependencies:
        for dependency in dependencies:
            lowered = str(dependency).lower()
            if lowered.startswith("mcp") or "mcp==1.27.2" in lowered:
                raise CheckFailure("trial MCP SDK dependency must not be present")
    scripts = project.get("scripts")
    if not isinstance(scripts, dict):
        raise CheckFailure("project scripts must be declared")
    if scripts.get("agentickvm") != "agentickvm.cli:main":
        raise CheckFailure("agentickvm CLI entry point must target agentickvm.cli:main")

    build_system = payload.get("build-system", {})
    if build_system.get("build-backend") != "setuptools.build_meta":
        raise CheckFailure("build backend must remain setuptools.build_meta")
    setuptools = payload.get("tool", {}).get("setuptools", {})
    package_find = setuptools.get("packages", {}).get("find", {})
    if package_find.get("where") != ["src"]:
        raise CheckFailure("package discovery must use src layout")


def _check_imports() -> None:
    package = importlib.import_module("agentickvm")
    if not hasattr(package, "__version__"):
        raise CheckFailure("agentickvm package must expose __version__")
    cli = importlib.import_module("agentickvm.cli")
    main = getattr(cli, "main", None)
    if not callable(main):
        raise CheckFailure("agentickvm.cli:main must be importable")
    if (ROOT / "src" / "agentickvm" / "__main__.py").exists():
        raise CheckFailure("python -m agentickvm behavior must be documented before enabling")


if __name__ == "__main__":
    raise SystemExit(main())
