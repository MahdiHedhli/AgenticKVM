from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _workflow_text(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_ci_workflow_is_mock_only_and_secret_free() -> None:
    workflow = _workflow_text("ci.yml")
    lowered = workflow.lower()

    assert "permissions:\n  contents: read" in workflow
    assert "python -m pytest" in workflow
    assert "python scripts/check-package.py" in workflow
    assert "python scripts/build-package.py" in workflow
    assert "python scripts/smoke-cli.py" in workflow
    assert "python scripts/lint-sanity.py" in workflow
    assert "python scripts/type-sanity.py" in workflow
    assert "python scripts/validate-docs.py" in workflow
    assert "python scripts/check-site.py" in workflow
    assert "secrets." not in lowered
    assert "mcp==1.27.2" not in lowered
    assert "run_stdio" not in lowered
    assert "live" not in lowered
    for forbidden in (
        "pikvm",
        "redfish",
        "rustdesk",
        "vnc",
        "rdp",
        "meshcentral",
        "idrac",
        "ilo",
        "ipmi",
        "supermicro",
        "proxmox",
    ):
        assert forbidden not in lowered


def test_ci_workflow_does_not_define_extra_permissions() -> None:
    workflow = _workflow_text("ci.yml")

    assert "pages: write" not in workflow
    assert "id-token: write" not in workflow
    assert "actions: write" not in workflow
    assert "contents: write" not in workflow


def test_pages_workflow_publishes_static_site_only() -> None:
    workflow = _workflow_text("pages.yml")
    lowered = workflow.lower()

    assert "contents: read" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "actions/upload-pages-artifact" in workflow
    assert "actions/deploy-pages" in workflow
    assert "path: site" in workflow
    assert "python -m pytest" not in workflow
    assert "pip install" not in lowered
    assert "uv run" not in lowered
    assert "secrets." not in lowered
    assert "mcp==1.27.2" not in lowered


def test_pages_workflow_does_not_reference_live_provider_commands() -> None:
    workflow = _workflow_text("pages.yml").lower()

    for forbidden in (
        "pikvm",
        "redfish",
        "rustdesk",
        "vnc",
        "rdp",
        "meshcentral",
        "idrac",
        "ilo",
        "ipmi",
        "supermicro",
        "proxmox",
        "smoke",
        "provider",
    ):
        assert forbidden not in workflow
