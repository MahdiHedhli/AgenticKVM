import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_release_manifest_generator_writes_json_to_explicit_temp_path(tmp_path: Path) -> None:
    output = tmp_path / "release-manifest.json"

    result = subprocess.run(
        [sys.executable, "scripts/generate-release-manifest.py", "--output", str(output)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    command_payload = json.loads(result.stdout)
    manifest = json.loads(output.read_text(encoding="utf-8"))

    assert command_payload["status"] == "ok"
    assert command_payload["output"] == str(output)
    assert manifest["project"]["name"] == "agentickvm"
    assert manifest["project"]["version"]
    assert manifest["git"]["branch"]
    assert manifest["checks"]["pytest"] == "not_run"
    assert manifest["docs"]["coverage_policy"] is True
    assert manifest["docs"]["sqlite_audit_hardening"] is True
    assert manifest["docs"]["live_provider_preflight"] is True
    assert manifest["docs"]["public_beta_risk_register"] is True
    assert manifest["docs"]["public_beta_readiness"] is True
    assert manifest["site"]["pages_workflow_static_site_only"] is True
    assert manifest["workflows"]["uses_secrets"] is False
    assert manifest["safety"]["live_providers_enabled"] is False
    assert manifest["safety"]["sdk_trial_dependency_present"] is False
    assert manifest["safety"]["credential_refs_resolved"] is False
    assert manifest["safety"]["live_provider_network_calls"] is False
    assert manifest["safety"]["live_provider_preflight_ci_block"] is True
    assert manifest["safety"]["generated_local_artifacts_committed"] is False


def test_release_manifest_generator_rejects_tracked_repo_paths() -> None:
    output = ROOT / "release-manifest.json"

    result = subprocess.run(
        [sys.executable, "scripts/generate-release-manifest.py", "--output", str(output)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "repo-local manifest output must be under ignored artifacts" in result.stderr
    assert not output.exists()


def test_release_manifest_generator_is_secret_free() -> None:
    source = (ROOT / "scripts" / "generate-release-manifest.py").read_text(
        encoding="utf-8"
    )

    assert "os.environ" not in source
    assert "requests" not in source
    assert "socket" not in source
    assert "resolve_credential" not in source
