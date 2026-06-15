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
        "Agentic Control Tower grants or denies clearance",
        "Out-of-band first",
        "clearance_required",
        "Live providers are deferred",
        "Killer demo",
        "not a mainline dependency",
        "Public beta is deferred",
        "What works today",
        "What is intentionally disabled",
        "https://github.com/MahdiHedhli/AgenticKVM/blob/main/docs/public-beta-known-limitations.md",
        "https://github.com/MahdiHedhli/AgenticKVM/blob/main/docs/public-beta-security-statement.md",
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
        "Future roadmap only",
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
        "<script",
    ):
        assert forbidden not in text

    for href in re.findall(r'href="(https?://[^"]+)"', text):
        assert href.startswith("https://github.com/mahdihedhli/agentickvm/")


def test_github_pages_site_links_resolve_locally() -> None:
    text = _site_text()
    ids = set(re.findall(r'id="([^"]+)"', text))
    hrefs = re.findall(r'href="([^"]+)"', text)

    for href in hrefs:
        if href.startswith("#"):
            assert href[1:] in ids
            continue
        if href.startswith("https://github.com/MahdiHedhli/AgenticKVM/"):
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


def test_github_pages_workflows_are_reviewed_and_safe() -> None:
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    workflows += sorted((ROOT / ".github" / "workflows").glob("*.yaml"))

    assert {path.name for path in workflows} <= {"ci.yml", "pages.yml"}
    for workflow in workflows:
        text = workflow.read_text(encoding="utf-8").lower()
        assert "secrets." not in text
        assert "mcp==1.27.2" not in text
        for forbidden in (
            "pikvm",
            "redfish",
            "rustdesk",
            "meshcentral",
            "idrac",
            "ipmi",
            "supermicro",
            "proxmox",
        ):
            assert forbidden not in text
