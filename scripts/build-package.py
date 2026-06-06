#!/usr/bin/env python3
"""Verify package artifact readiness without adding build dependencies.

If the `build` module is available, this script builds a wheel and sdist into a
temporary directory and validates their shape. If `build` is unavailable, it
reports a documented deferred status and exits successfully unless
`--require-build` is passed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
FORBIDDEN_TEXT = (
    "mcp==1.27.2",
    "fully supports live pikvm",
    "fully supports live redfish",
    "supports rdp today",
    "supports vnc today",
    "supports rustdesk today",
    "supports meshcentral today",
)
FORBIDDEN_ARTIFACT_ENTRIES = (
    "__pycache__",
    ".pyc",
    "artifacts/",
    "agentickvm-artifacts",
    "screenshots/",
    ".screenshot.",
    "audit.jsonl",
)


class BuildCheckFailure(RuntimeError):
    """Raised when package artifact validation fails."""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--require-build",
        action="store_true",
        help="fail if the optional build module is unavailable",
    )
    args = parser.parse_args()

    try:
        result = _check_package_artifacts(require_build=args.require_build)
    except Exception as exc:
        print(f"package artifact check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _check_package_artifacts(*, require_build: bool) -> dict[str, Any]:
    metadata = _metadata_summary()
    if importlib.util.find_spec("build") is None:
        if require_build:
            raise BuildCheckFailure("python build module is not installed")
        return {
            "status": "deferred",
            "reason": "python build module is not installed",
            "build_module_available": False,
            "project": metadata,
        }

    with tempfile.TemporaryDirectory(prefix="agentickvm-build-") as tmpdir:
        outdir = Path(tmpdir)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--sdist",
                "--wheel",
                "--outdir",
                str(outdir),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        artifacts = sorted(outdir.iterdir())
        wheels = [path for path in artifacts if path.suffix == ".whl"]
        sdists = [path for path in artifacts if path.name.endswith(".tar.gz")]
        if len(wheels) != 1:
            raise BuildCheckFailure("expected exactly one wheel artifact")
        if len(sdists) != 1:
            raise BuildCheckFailure("expected exactly one sdist artifact")
        for artifact in artifacts:
            _validate_artifact_path(artifact)
            _validate_artifact_contents(artifact)
        _verify_import_from_wheel(wheels[0])
        return {
            "status": "built",
            "build_module_available": True,
            "project": metadata,
            "artifacts": [artifact.name for artifact in artifacts],
        }


def _metadata_summary() -> dict[str, Any]:
    payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = payload.get("project", {})
    if not isinstance(project, dict):
        raise BuildCheckFailure("missing [project] metadata")
    name = project.get("name")
    version = project.get("version")
    description = str(project.get("description", ""))
    dependencies = project.get("dependencies", [])
    if name != "agentickvm":
        raise BuildCheckFailure("project name must be agentickvm")
    if not isinstance(version, str) or not version:
        raise BuildCheckFailure("project version is required")
    if any("mcp==1.27.2" in str(dep).lower() for dep in dependencies):
        raise BuildCheckFailure("trial MCP SDK dependency must not be present")
    lowered_description = description.lower()
    for phrase in FORBIDDEN_TEXT:
        if phrase in lowered_description:
            raise BuildCheckFailure(f"package metadata overclaims {phrase!r}")
    return {
        "name": name,
        "version": version,
        "requires_python": project.get("requires-python"),
        "dependency_count": len(dependencies),
        "scripts": sorted((project.get("scripts") or {}).keys()),
        "live_providers_enabled": False,
        "sdk_trial_dependency_present": False,
    }


def _validate_artifact_path(path: Path) -> None:
    if not path.is_file():
        raise BuildCheckFailure(f"artifact is not a file: {path.name}")
    if not path.name.startswith("agentickvm-"):
        raise BuildCheckFailure(f"unexpected artifact name: {path.name}")


def _validate_artifact_contents(path: Path) -> None:
    names = _artifact_names(path)
    for name in names:
        lowered = name.lower()
        if any(fragment in lowered for fragment in FORBIDDEN_ARTIFACT_ENTRIES):
            raise BuildCheckFailure(f"artifact contains forbidden generated path: {name}")

    data = path.read_bytes().lower()
    for phrase in FORBIDDEN_TEXT:
        if phrase.encode() in data:
            raise BuildCheckFailure(f"artifact contains forbidden text: {phrase}")


def _artifact_names(path: Path) -> list[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()
    if path.name.endswith(".tar.gz"):
        with tarfile.open(path, mode="r:gz") as archive:
            return archive.getnames()
    raise BuildCheckFailure(f"unsupported artifact type: {path.name}")


def _verify_import_from_wheel(wheel: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(wheel)
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import agentickvm, agentickvm.cli; assert agentickvm.__version__",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
