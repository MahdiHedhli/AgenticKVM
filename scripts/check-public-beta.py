#!/usr/bin/env python3
"""Validate public beta cutover readiness.

This script is dependency-free and repo-local. It writes generated output only
to a temporary directory and does not read credentials or contact providers.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

REQUIRED_FILES = (
    "CHANGELOG.md",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "docs/public-beta-cutover-plan.md",
    "docs/releases/public-beta-0.1.0.md",
    "docs/public-beta-known-limitations.md",
    "docs/public-beta-security-statement.md",
    "docs/github-pages-enablement-checklist.md",
    "docs/maintainer-runbook.md",
    "docs/public-beta-merge-review.md",
    "docs/public-beta-readiness.md",
    "docs/public-beta-risk-register.md",
    "docs/public-beta-final-review.md",
    "docs/public-beta-merge-commands.md",
    "docs/public-beta-tagging-plan.md",
    "docs/public-beta-final-handoff.md",
    "docs/act-clearance-client.md",
    "site/index.html",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/security_report.md",
    ".github/pull_request_template.md",
)

SITE_REQUIRED_SNIPPETS = (
    "https://github.com/MahdiHedhli/AgenticKVM/blob/main/docs/releases/public-beta-0.1.0.md",
    "https://github.com/MahdiHedhli/AgenticKVM/blob/main/docs/public-beta-known-limitations.md",
    "https://github.com/MahdiHedhli/AgenticKVM/blob/main/docs/public-beta-security-statement.md",
    "Agentic Control Tower",
    "ACT clearance",
    "Killer demo",
    "Live providers are deferred",
)

FORBIDDEN_TRACKED_SUFFIXES = (
    ".sqlite",
    ".sqlite3",
    ".db",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
)

FORBIDDEN_WORKFLOW_SNIPPETS = (
    "secrets.",
    "mcp==1.27.2",
    "pikvm",
    "redfish",
    "rustdesk",
    "meshcentral",
    "idrac",
    "ilo",
    "ipmi",
    "supermicro",
    "proxmox",
)


class PublicBetaFailure(RuntimeError):
    """Raised when public beta readiness fails."""


def main() -> int:
    try:
        payload = {
            "required_files": _check_required_files(),
            "metadata": _check_metadata(),
            "site": _check_site_links(),
            "templates": _check_templates(),
            "manifest": _check_manifest_generation(),
            "tracked_artifacts": _check_tracked_artifacts(),
            "workflows": _check_workflows(),
        }
    except Exception as exc:
        print(f"public beta check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", **payload}, sort_keys=True))
    return 0


def _check_required_files() -> int:
    missing = [path for path in REQUIRED_FILES if not (ROOT / path).exists()]
    if missing:
        raise PublicBetaFailure(f"missing required public beta files: {', '.join(missing)}")
    return len(REQUIRED_FILES)


def _check_metadata() -> dict[str, Any]:
    payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = payload.get("project", {})
    dependencies = [str(item).lower() for item in project.get("dependencies", [])]
    if any(item.startswith("mcp") or "mcp==1.27.2" in item for item in dependencies):
        raise PublicBetaFailure("SDK trial dependency must not be present")
    return {
        "project": project.get("name"),
        "version": project.get("version"),
        "sdk_trial_dependency_present": False,
        "dependency_count": len(dependencies),
    }


def _check_site_links() -> dict[str, bool]:
    site = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    for snippet in SITE_REQUIRED_SNIPPETS:
        if snippet not in site:
            raise PublicBetaFailure(f"site missing public beta snippet: {snippet}")
    return {
        "release_notes_linked": True,
        "known_limitations_linked": True,
        "security_statement_linked": True,
    }


def _check_templates() -> dict[str, bool]:
    combined = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in (
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            ".github/ISSUE_TEMPLATE/security_report.md",
            ".github/pull_request_template.md",
        )
    ).lower()
    for snippet in ("do not", "secrets", "credentials", "real hostnames", "real ip"):
        if snippet not in combined:
            raise PublicBetaFailure(f"templates missing safety warning: {snippet}")
    return {"secret_warning_present": True}


def _check_manifest_generation() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="agentickvm-public-beta-") as temp_dir:
        output = Path(temp_dir) / "manifest.json"
        result = subprocess.run(
            [
                sys.executable,
                "scripts/generate-release-manifest.py",
                "--output",
                str(output),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        command_payload = json.loads(result.stdout)
        manifest = json.loads(output.read_text(encoding="utf-8"))
    if manifest["release"]["channel"] != "public-beta":
        raise PublicBetaFailure("manifest must report public beta channel")
    if manifest["safety"]["live_providers_enabled"] is not False:
        raise PublicBetaFailure("manifest must report live providers disabled")
    if manifest["safety"]["sdk_trial_dependency_present"] is not False:
        raise PublicBetaFailure("manifest must report no SDK trial dependency")
    return {
        "generated": command_payload["status"] == "ok",
        "tag_proposal": manifest["release"]["tag_proposal"],
    }


def _check_tracked_artifacts() -> dict[str, int]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    offenders: list[str] = []
    for path in result.stdout.splitlines():
        if path.startswith("tests/fixtures/"):
            continue
        lowered = path.lower()
        if lowered.endswith(FORBIDDEN_TRACKED_SUFFIXES):
            offenders.append(path)
        if lowered.endswith(".json") and any(
            marker in lowered
            for marker in (
                "manifest",
                "audit-export",
                "audit-checkpoint",
                "approval-queue",
                "approval_queue",
            )
        ):
            offenders.append(path)
    if offenders:
        raise PublicBetaFailure(
            "generated local artifacts must not be tracked: " + ", ".join(offenders)
        )
    return {"tracked_generated_artifacts": 0}


def _check_workflows() -> dict[str, bool]:
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8").lower()
    pages = (
        ROOT / ".github" / "workflows" / "pages.yml"
    ).read_text(encoding="utf-8").lower()
    for workflow_name, text in (("ci", ci), ("pages", pages)):
        for snippet in FORBIDDEN_WORKFLOW_SNIPPETS:
            if snippet in text:
                raise PublicBetaFailure(f"{workflow_name} workflow contains {snippet}")
    if "path: site" not in pages:
        raise PublicBetaFailure("Pages workflow must publish site/")
    if "python scripts/check-public-beta.py" not in ci:
        raise PublicBetaFailure("CI workflow must run public beta check")
    return {"ci_safe": True, "pages_safe": True}


if __name__ == "__main__":
    raise SystemExit(main())
