import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_site_preview_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check-site.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["anchors"] > 0
    assert payload["links"] > 0
    assert payload["scripts"] == 0
    assert payload["tracking"] is False
    assert payload["remote_fonts"] is False
    assert payload["pages_workflow_static_site_only"] is True


def test_site_preview_script_is_static_and_secret_free() -> None:
    source = (ROOT / "scripts" / "check-site.py").read_text(encoding="utf-8")

    assert "requests" not in source
    assert "socket" not in source
    assert "os.environ" not in source
    assert "secrets." in source
    assert "mcp==1.27.2" in source


def test_site_preview_docs_exist() -> None:
    assert (ROOT / "docs" / "site-preview.md").exists()
