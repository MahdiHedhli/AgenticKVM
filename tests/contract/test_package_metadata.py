import subprocess
import sys
import tomllib
from importlib import import_module
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_project_metadata_is_release_gate_ready() -> None:
    project = _pyproject()["project"]

    assert project["name"] == "agentickvm"
    assert project["requires-python"] == ">=3.11"
    assert project["scripts"]["agentickvm"] == "agentickvm.cli:main"
    assert "mcp==1.27.2" not in repr(project).lower()
    assert not any(str(dep).lower().startswith("mcp") for dep in project.get("dependencies", []))


def test_package_and_cli_import_without_trial_sdk_dependency() -> None:
    package = import_module("agentickvm")
    cli = import_module("agentickvm.cli")

    assert package.__version__ == "0.0.0"
    assert callable(cli.main)
    assert import_module("agentickvm.mcp_sdk")


def test_python_module_entrypoint_is_not_enabled_accidentally() -> None:
    assert not (ROOT / "src" / "agentickvm" / "__main__.py").exists()


def test_package_check_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check-package.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "package check passed"
    assert result.stderr == ""
