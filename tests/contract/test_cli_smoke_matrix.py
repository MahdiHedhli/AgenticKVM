import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_cli_smoke_matrix_passes_with_expected_cases() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/smoke-cli.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    cases = {case["name"]: case for case in payload["cases"]}

    assert payload["status"] == "ok"
    assert cases["list-providers"]["status"] == "ok"
    assert cases["list-targets"]["status"] == "ok"
    assert cases["mock-observe-screen"]["status"] == "ok"
    assert cases["mock-power-state"]["status"] == "ok"
    assert cases["pikvm-fixture-observe-screen"]["status"] == "ok"
    assert cases["unknown-tool"]["status"] == "validation_error"
    assert cases["unknown-target"]["status"] == "validation_error"
    assert cases["disabled-provider-target"]["status"] == "validation_error"
    assert cases["dangerous-action-gated"]["status"] == "approval_required"
    assert cases["raw-secret-reveal-denied"]["status"] == "denied"
    assert cases["policy-modification-denied"]["status"] == "denied"


def test_cli_smoke_matrix_output_is_json_safe_and_redacted() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/smoke-cli.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    json.loads(json.dumps(json.loads(result.stdout), sort_keys=True))
    lowered = result.stdout.lower()
    assert "mcp==1.27.2" not in lowered
    assert "password" not in lowered
    assert "api_key" not in lowered
    assert "private_key" not in lowered
    assert "bearer " not in lowered


def test_cli_smoke_script_is_mock_only() -> None:
    source = (ROOT / "scripts" / "smoke-cli.py").read_text(encoding="utf-8")

    assert "os.environ" not in source
    assert "requests" not in source
    assert "socket" not in source
    assert "execute_authorized" not in source
    assert "credential_ref" not in source
