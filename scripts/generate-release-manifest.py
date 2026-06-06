#!/usr/bin/env python3
"""Generate a JSON release manifest for human review."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
SAFE_REPO_OUTPUT_DIRS = {"artifacts", "agentickvm-artifacts"}


class ManifestFailure(RuntimeError):
    """Raised when release manifest generation is unsafe."""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="Explicit manifest output path")
    args = parser.parse_args()

    try:
        output = Path(args.output).expanduser()
        _validate_output_path(output)
        manifest = _manifest()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"release manifest generation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "output": str(output)}, sort_keys=True))
    return 0


def _validate_output_path(output: Path) -> None:
    if output.exists() and output.is_dir():
        raise ManifestFailure("manifest output must be a file path")
    resolved = output.resolve()
    try:
        relative = resolved.relative_to(ROOT)
    except ValueError:
        return
    if not relative.parts:
        raise ManifestFailure("manifest output must not be the repository root")
    if relative.parts[0] not in SAFE_REPO_OUTPUT_DIRS:
        raise ManifestFailure(
            "repo-local manifest output must be under ignored artifacts/ directories"
        )


def _manifest() -> dict[str, Any]:
    metadata = _project_metadata()
    workflow_text = _workflow_text()
    return {
        "schema_version": "0.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "project": metadata,
        "git": {
            "branch": _git(["branch", "--show-current"]),
            "commit": _git(["rev-parse", "HEAD"]),
        },
        "checks": {
            "package_check": "not_run",
            "package_artifact_check": "not_run",
            "cli_smoke": "not_run",
            "lint_sanity": "not_run",
            "type_sanity": "not_run",
            "docs_validation": "not_run",
            "pytest": "not_run",
        },
        "docs": {
            "release_readiness": (ROOT / "docs" / "release-readiness.md").exists(),
            "release_checklist": (ROOT / "docs" / "release-checklist.md").exists(),
            "coverage_policy": (ROOT / "docs" / "coverage-policy.md").exists(),
            "sqlite_audit_hardening": (
                ROOT / "docs" / "sqlite-audit-hardening.md"
            ).exists(),
            "live_provider_preflight": (
                ROOT / "docs" / "live-provider-preflight.md"
            ).exists(),
            "public_beta_risk_register": (
                ROOT / "docs" / "public-beta-risk-register.md"
            ).exists(),
            "public_beta_readiness": (
                ROOT / "docs" / "public-beta-readiness.md"
            ).exists(),
            "public_beta_merge_review": (
                ROOT / "docs" / "public-beta-merge-review.md"
            ).exists(),
        },
        "site": {
            "site_dir": (ROOT / "site").exists(),
            "index": (ROOT / "site" / "index.html").exists(),
            "styles": (ROOT / "site" / "styles.css").exists(),
            "pages_workflow_static_site_only": "path: site" in workflow_text,
        },
        "workflows": {
            "ci_workflow": (ROOT / ".github" / "workflows" / "ci.yml").exists(),
            "pages_workflow": (ROOT / ".github" / "workflows" / "pages.yml").exists(),
            "uses_secrets": "secrets." in workflow_text.lower(),
        },
        "safety": {
            "live_providers_enabled": False,
            "sdk_trial_dependency_present": metadata["sdk_trial_dependency_present"],
            "credential_refs_resolved": False,
            "live_provider_network_calls": False,
            "requires_github_actions_secrets": "secrets." in workflow_text.lower(),
            "live_provider_preflight_ci_block": True,
            "generated_local_artifacts_committed": False,
        },
    }


def _project_metadata() -> dict[str, Any]:
    payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = payload.get("project", {})
    dependencies = project.get("dependencies", [])
    sdk_trial_dependency_present = any(
        "mcp==1.27.2" in str(dependency).lower() for dependency in dependencies
    )
    return {
        "name": project.get("name"),
        "version": project.get("version"),
        "requires_python": project.get("requires-python"),
        "dependency_count": len(dependencies),
        "scripts": sorted((project.get("scripts") or {}).keys()),
        "sdk_trial_dependency_present": sdk_trial_dependency_present,
    }


def _workflow_text() -> str:
    workflow_dir = ROOT / ".github" / "workflows"
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(workflow_dir.glob("*.yml"))
    )


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
