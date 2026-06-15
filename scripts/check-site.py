#!/usr/bin/env python3
"""Validate the static GitHub Pages site for safe preview."""

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
INDEX = SITE / "index.html"
STYLES = SITE / "styles.css"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"

FORBIDDEN_TEXT = (
    "google-analytics",
    "googletagmanager",
    "gtag(",
    "plausible",
    "segment.com",
    "analytics",
    "fonts.googleapis",
    "fonts.gstatic",
    "<script",
    "production ready",
    "fully supports live pikvm",
    "fully supports live redfish",
    "supports rdp today",
    "supports vnc today",
    "supports rustdesk today",
    "supports meshcentral today",
    "zero risk",
    "mcp==1.27.2",
)
ALLOWED_REMOTE_PREFIXES = (
    "https://github.com/MahdiHedhli/AgenticKVM/blob/main/",
    "https://github.com/MahdiHedhli/AgenticKVM/tree/main/",
)


class SiteFailure(RuntimeError):
    """Raised when site preview validation fails."""


class SiteHTMLParser(HTMLParser):
    """Collect basic HTML structure for preview validation."""

    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.hrefs: list[str] = []
        self.scripts: list[dict[str, str]] = []
        self.meta_viewport = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        if "id" in attrs_dict:
            self.ids.add(attrs_dict["id"])
        if tag == "a" and "href" in attrs_dict:
            self.hrefs.append(attrs_dict["href"])
        if tag == "script":
            self.scripts.append(attrs_dict)
        if tag == "meta" and attrs_dict.get("name") == "viewport":
            self.meta_viewport = True


def main() -> int:
    try:
        payload = _check_site()
    except Exception as exc:
        print(f"site preview check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0


def _check_site() -> dict[str, Any]:
    if not INDEX.exists():
        raise SiteFailure("site/index.html is missing")
    if not STYLES.exists():
        raise SiteFailure("site/styles.css is missing")
    html = INDEX.read_text(encoding="utf-8")
    css = STYLES.read_text(encoding="utf-8")
    lowered = (html + "\n" + css).lower()

    parser = SiteHTMLParser()
    parser.feed(html)
    if not parser.meta_viewport:
        raise SiteFailure("site is missing mobile viewport metadata")
    if parser.scripts:
        raise SiteFailure("site must not include script tags")
    for forbidden in FORBIDDEN_TEXT:
        if forbidden in lowered:
            raise SiteFailure(f"site contains forbidden text {forbidden!r}")
    _check_local_links(parser)
    _check_provider_language(html)
    _check_pages_workflow()
    return {
        "status": "ok",
        "anchors": len(parser.ids),
        "links": len(parser.hrefs),
        "scripts": 0,
        "tracking": False,
        "remote_fonts": False,
        "pages_workflow_static_site_only": True,
    }


def _check_local_links(parser: SiteHTMLParser) -> None:
    for href in parser.hrefs:
        if href.startswith("#"):
            if href[1:] not in parser.ids:
                raise SiteFailure(f"broken local anchor: {href}")
            continue
        if re.match(r"https?://", href, flags=re.I):
            if href.startswith(ALLOWED_REMOTE_PREFIXES):
                continue
            raise SiteFailure(f"remote link requires review: {href}")
        if not (SITE / href).resolve().exists():
            raise SiteFailure(f"broken local link: {href}")


def _check_provider_language(html: str) -> None:
    required = (
        "Live providers are deferred",
        "Killer demo",
        "Not on the AgenticKVM roadmap",
        "observe-only readiness/spec stages",
        "not a mainline dependency",
    )
    for snippet in required:
        if snippet not in html:
            raise SiteFailure(f"site missing provider roadmap language: {snippet}")


def _check_pages_workflow() -> None:
    workflow = PAGES_WORKFLOW.read_text(encoding="utf-8").lower()
    if "path: site" not in workflow:
        raise SiteFailure("Pages workflow must publish site/")
    if "secrets." in workflow:
        raise SiteFailure("Pages workflow must not reference secrets")
    if "pip install" in workflow or "python -m pytest" in workflow:
        raise SiteFailure("Pages workflow must not install dependencies or run tests")


if __name__ == "__main__":
    raise SystemExit(main())
