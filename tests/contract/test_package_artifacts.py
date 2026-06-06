import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_package_artifact_gate_reports_built_or_deferred_status() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build-package.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] in {"built", "deferred"}
    assert payload["project"]["name"] == "agentickvm"
    assert payload["project"]["version"]
    assert payload["project"]["live_providers_enabled"] is False
    assert payload["project"]["sdk_trial_dependency_present"] is False
    assert "mcp==1.27.2" not in result.stdout.lower()
    if payload["status"] == "built":
        assert payload["build_module_available"] is True
        assert any(name.endswith(".whl") for name in payload["artifacts"])
        assert any(name.endswith(".tar.gz") for name in payload["artifacts"])
    else:
        assert payload["build_module_available"] is False
        assert payload["reason"] == "python build module is not installed"


def test_package_artifact_gate_can_require_build_tooling() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build-package.py", "--require-build"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    if importlib.util.find_spec("build") is None:
        assert result.returncode != 0
        assert "python build module is not installed" in result.stderr
        assert "mcp==1.27.2" not in result.stderr.lower()
    else:
        assert result.returncode == 0
        assert json.loads(result.stdout)["status"] == "built"


def test_package_artifact_gate_does_not_write_tracked_dist_paths() -> None:
    for relative in ("dist", "build"):
        path = ROOT / relative
        assert not path.exists()
