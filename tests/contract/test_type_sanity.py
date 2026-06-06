import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_type_sanity_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/type-sanity.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["imported_modules"] >= 10
    assert payload["dataclasses_checked"] >= 10
    assert payload["json_shapes_checked"] >= 5
    assert payload["sdk_trial_dependency_imported"] is False
    assert "mcp==1.27.2" not in result.stdout.lower()


def test_type_sanity_script_does_not_import_trial_sdk() -> None:
    source = (ROOT / "scripts" / "type-sanity.py").read_text(encoding="utf-8")

    assert "import mcp" not in source
    assert "from mcp" not in source
    assert "requests" not in source
    assert "socket" not in source
