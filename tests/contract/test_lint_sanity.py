import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_lint_sanity_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/lint-sanity.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["checked"]["python_files"] > 0
    assert payload["checked"]["text_files"] > 0
    assert payload["checked"]["metadata"]["sdk_trial_dependency_present"] is False
    assert "mcp==1.27.2" not in result.stdout.lower()


def test_lint_sanity_script_is_dependency_free() -> None:
    source = (ROOT / "scripts" / "lint-sanity.py").read_text(encoding="utf-8")

    assert "requests" not in source
    assert "socket" not in source
    assert "subprocess" not in source
    assert "import ast" in source
    assert "import json" in source
