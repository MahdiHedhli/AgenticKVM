#!/usr/bin/env python3
"""Run dependency-free lint sanity checks."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIRS = ("src", "tests", "scripts")
TEXT_DIRS = ("docs", "examples", "site")
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv"}
GENERATED_LOCAL_ARTIFACT_SUFFIXES = (
    ".sqlite",
    ".sqlite3",
    ".db",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
)
GENERATED_LOCAL_ARTIFACT_NAMES = {
    "approvals.json",
    "approval-queue.json",
    "approval_queue.json",
    "audit-export.json",
    "audit_export.json",
    "audit-checkpoint.json",
    "audit_checkpoint.json",
    "release-manifest.json",
}
DEBUG_PATTERNS = (
    "pdb" + ".set_trace",
    "ipdb" + ".set_trace",
    "break" + "point(",
    "TODO" + "_DEBUG",
    "DEBUG" + "_ONLY",
)
SECRET_KEY_PATTERNS = (
    re.compile(r'"(?:password|token|api_key|private_key|bearer|session_cookie)"\s*:', re.I),
    re.compile(r"\b(?:password|token|api_key|private_key|bearer|session_cookie)\s*=", re.I),
)
FORBIDDEN_PUBLIC_CLAIMS = (
    "production ready",
    "fully supports live pikvm",
    "fully supports live redfish",
    "supports rdp today",
    "supports vnc today",
    "supports rustdesk today",
    "supports meshcentral today",
    "autonomous production recovery",
    "zero risk",
)
FORBIDDEN_LIVE_URL_RE = re.compile(r"https?://([^\\s\"')<>]+)", re.I)


class LintSanityFailure(RuntimeError):
    """Raised when lint sanity checks fail."""


def main() -> int:
    try:
        checked = {
            "python_files": _check_python_files(),
            "text_files": _check_text_files(),
            "metadata": _check_metadata(),
            "generated_local_artifacts": _check_generated_local_artifacts(),
        }
    except Exception as exc:
        print(f"lint sanity failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "checked": checked}, sort_keys=True))
    return 0


def _check_python_files() -> int:
    count = 0
    for path in _paths(PYTHON_DIRS, suffixes=(".py",)):
        count += 1
        text = path.read_text(encoding="utf-8")
        try:
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            raise LintSanityFailure(f"python syntax error in {path}: {exc}") from exc
        lowered = text.lower()
        for pattern in DEBUG_PATTERNS:
            if pattern.lower() in lowered:
                raise LintSanityFailure(f"debug leftover {pattern!r} in {path}")
    return count


def _check_text_files() -> int:
    count = 0
    for path in _paths(TEXT_DIRS, suffixes=(".md", ".html", ".css", ".yaml", ".json", ".txt")):
        count += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        lowered = text.lower()
        if path.parts[-2:] == ("site", "index.html") or path.name == "README.md":
            for claim in FORBIDDEN_PUBLIC_CLAIMS:
                if claim in lowered:
                    raise LintSanityFailure(f"public overclaim {claim!r} in {path}")
        if path.parts[0] in {"examples", "site"}:
            for pattern in SECRET_KEY_PATTERNS:
                match = pattern.search(text)
                if match:
                    raise LintSanityFailure(
                        f"secret-like key {match.group(0)!r} in {path}"
                    )
            _check_live_urls(path, text)
    return count


def _check_live_urls(path: Path, text: str) -> None:
    for match in FORBIDDEN_LIVE_URL_RE.finditer(text):
        host = match.group(1).split("/", 1)[0].lower()
        if host.endswith("example.invalid"):
            continue
        if host in {"github.com", "www.github.com"}:
            continue
        raise LintSanityFailure(f"non-documentation URL {match.group(0)!r} in {path}")


def _check_metadata() -> dict[str, bool]:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    if "mcp==1.27.2" in pyproject:
        raise LintSanityFailure("trial MCP SDK dependency is present")
    return {"sdk_trial_dependency_present": False}


def _check_generated_local_artifacts() -> dict[str, int]:
    offenders: list[str] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if relative.parts[:2] == ("tests", "fixtures"):
            continue
        lowered_name = path.name.lower()
        if path.suffix.lower() in GENERATED_LOCAL_ARTIFACT_SUFFIXES:
            offenders.append(str(relative))
        elif lowered_name in GENERATED_LOCAL_ARTIFACT_NAMES:
            offenders.append(str(relative))
        elif "screenshot" in lowered_name and path.suffix.lower() in {".json", ".txt"}:
            offenders.append(str(relative))
    if offenders:
        raise LintSanityFailure(
            "generated local audit/approval/artifact files must not be committed: "
            + ", ".join(offenders)
        )
    return {"committed_generated_artifacts": 0}


def _paths(root_names: Iterable[str], *, suffixes: tuple[str, ...]) -> Iterable[Path]:
    for root_name in root_names:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if any(part in SKIP_PARTS for part in relative.parts):
                continue
            if path.suffix in suffixes:
                yield relative


if __name__ == "__main__":
    raise SystemExit(main())
