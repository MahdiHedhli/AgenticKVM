import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_public_beta_readiness_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check-public-beta.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["required_files"] >= 20
    assert payload["metadata"]["sdk_trial_dependency_present"] is False
    assert payload["site"]["known_limitations_linked"] is True
    assert payload["templates"]["secret_warning_present"] is True
    assert payload["manifest"]["tag_proposal"] == "v0.1.0-public-beta.1"
    assert payload["tracked_artifacts"]["tracked_generated_artifacts"] == 0
    assert payload["workflows"]["ci_safe"] is True
    assert payload["workflows"]["pages_safe"] is True


def test_public_beta_readiness_script_is_secret_and_network_free() -> None:
    source = (ROOT / "scripts" / "check-public-beta.py").read_text(encoding="utf-8")

    assert "requests" not in source
    assert "socket" not in source
    assert "os.environ" not in source
    assert "resolve_credential" not in source
