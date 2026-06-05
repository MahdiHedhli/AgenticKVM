import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_docs_validation_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate-docs.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "docs validation passed"
    assert result.stderr == ""


def test_required_release_quality_docs_exist() -> None:
    for relative in (
        "docs/release-quality-gates.md",
        "docs/github-pages.md",
        "docs/packaging.md",
        "site/index.html",
        "site/styles.css",
    ):
        assert (ROOT / relative).exists()
