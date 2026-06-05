import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"
INDEX = SITE / "index.html"


def _site_text() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_github_pages_site_files_exist() -> None:
    assert INDEX.exists()
    assert (SITE / "styles.css").exists()
    assert (SITE / "README.md").exists()
    assert (ROOT / "docs" / "github-pages.md").exists()


def test_github_pages_site_contains_required_safety_messaging() -> None:
    text = _site_text()

    for required in (
        "Give your AI agent hands for real machines.",
        "Safety guardrails built in.",
        "Policy, approvals, audit, and provider registries before execution.",
        "Out-of-band first",
        "approval_required",
        "Live providers are deferred",
        "Future roadmap only",
        "not a mainline dependency",
    ):
        assert required in text


def test_github_pages_site_does_not_overclaim_live_support() -> None:
    text = _site_text().lower()

    for forbidden in (
        "production ready",
        "fully supports live pikvm",
        "fully supports live redfish",
        "supports rdp today",
        "supports vnc today",
        "supports rustdesk today",
        "supports meshcentral today",
        "autonomous recovery without human approval",
        "secure by default",
        "zero risk",
        "hands-off production operation",
    ):
        assert forbidden not in text


def test_github_pages_site_has_no_tracking_or_remote_assets() -> None:
    text = _site_text().lower()

    for forbidden in (
        "google-analytics",
        "googletagmanager",
        "gtag(",
        "plausible",
        "segment.com",
        "analytics",
        "http://",
        "https://",
        "<script",
    ):
        assert forbidden not in text


def test_github_pages_site_links_resolve_locally() -> None:
    text = _site_text()
    ids = set(re.findall(r'id="([^"]+)"', text))
    hrefs = re.findall(r'href="([^"]+)"', text)

    for href in hrefs:
        if href.startswith("#"):
            assert href[1:] in ids
            continue
        path = (SITE / href).resolve()
        assert path.exists(), href


def test_github_pages_site_does_not_add_trial_sdk_dependency_to_mainline() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "mcp==1.27.2" not in pyproject
    assert '"mcp' not in pyproject
    assert "mcp.server.fastmcp" not in "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in SITE.glob("*")
        if path.is_file()
    )


def test_github_pages_workflow_is_not_added_without_review() -> None:
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    workflows += sorted((ROOT / ".github" / "workflows").glob("*.yaml"))

    assert workflows == []
