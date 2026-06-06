import json
from pathlib import Path

from agentickvm.cli import main
from agentickvm.providers import (
    LiveProviderPreflightRequest,
    PreflightStatus,
    run_live_provider_preflight,
)


def _ready_request(tmp_path: Path, **overrides: object) -> LiveProviderPreflightRequest:
    repo_root = tmp_path / "repo"
    external_config = tmp_path / "operator" / "pikvm-live.json"
    artifact_path = tmp_path / "operator-artifacts"
    payload = {
        "provider_type": "pikvm",
        "provider_id": "pikvm-lab",
        "target_id": "pikvm-target",
        "live_provider_enabled": True,
        "external_config_path": str(external_config),
        "credential_ref": "prompt://operator/pikvm",
        "audit_backend_configured": True,
        "approval_transport_configured": True,
        "artifact_path": str(artifact_path),
        "tls_policy_reviewed": True,
        "timeout_policy_reviewed": True,
        "manual_smoke_acknowledged": True,
        "ci_mode": False,
        "test_mode": False,
        "committed_config_provider_enabled": False,
        "capabilities": ("observe.status", "observe.screen"),
        "repo_root": str(repo_root),
    }
    payload.update(overrides)
    return LiveProviderPreflightRequest(**payload)


def _write_disabled_pikvm_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "pikvm-disabled.json"
    config_path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "pikvm-lab",
                        "type": "pikvm",
                        "enabled": False,
                        "credential_ref": "prompt://operator/pikvm",
                        "metadata": {
                            "live_mode": True,
                            "capabilities": ["observe.status", "observe.screen"],
                        },
                    }
                ],
                "targets": [
                    {
                        "id": "pikvm-target",
                        "provider": "pikvm-lab",
                        "enabled": True,
                        "allowed_modes": ["Observe"],
                    }
                ],
                "default_policy": {"mode": "Observe"},
            }
        ),
        encoding="utf-8",
    )
    return config_path


def test_preflight_passes_only_with_complete_operator_evidence(tmp_path) -> None:
    result = run_live_provider_preflight(_ready_request(tmp_path))

    assert result.status == PreflightStatus.OK
    assert result.ok is True
    payload = result.to_dict()
    assert payload["provider_id"] == "pikvm-lab"
    assert "prompt://operator/pikvm" not in repr(payload)


def test_preflight_blocks_ci_and_test_mode(tmp_path) -> None:
    result = run_live_provider_preflight(
        _ready_request(tmp_path, ci_mode=True, test_mode=True)
    )

    assert result.status == PreflightStatus.BLOCKED
    assert "CI mode blocks live provider preflight" in result.blockers
    assert "test mode blocks live provider preflight" in result.blockers


def test_preflight_requires_core_gate_evidence(tmp_path) -> None:
    result = run_live_provider_preflight(
        _ready_request(
            tmp_path,
            live_provider_enabled=False,
            external_config_path=None,
            credential_ref=None,
            audit_backend_configured=False,
            approval_transport_configured=False,
            tls_policy_reviewed=False,
            timeout_policy_reviewed=False,
            manual_smoke_acknowledged=False,
        )
    )

    assert result.status == PreflightStatus.BLOCKED
    assert "live provider must be explicitly enabled outside defaults" in result.blockers
    assert "external config path is required" in result.blockers
    assert "credential_ref is required" in result.blockers
    assert "audit backend is required" in result.blockers
    assert "approval transport is required" in result.blockers
    assert "TLS policy review is required" in result.blockers
    assert "timeout policy review is required" in result.blockers
    assert "manual smoke gate must be acknowledged" in result.blockers


def test_preflight_rejects_relative_and_repo_artifact_paths(tmp_path) -> None:
    relative = run_live_provider_preflight(
        _ready_request(tmp_path, external_config_path="relative/config.json")
    )
    assert "external config path must be absolute" in relative.blockers

    repo_root = tmp_path / "repo"
    artifact_inside_repo = repo_root / "artifacts"
    result = run_live_provider_preflight(
        _ready_request(
            tmp_path,
            repo_root=str(repo_root),
            artifact_path=str(artifact_inside_repo),
        )
    )

    assert result.status == PreflightStatus.BLOCKED
    assert "artifact path must not point inside the repository" in result.blockers


def test_preflight_rejects_committed_live_enablement_and_mutating_capabilities(tmp_path) -> None:
    result = run_live_provider_preflight(
        _ready_request(
            tmp_path,
            committed_config_provider_enabled=True,
            capabilities=("observe.status", "power.force_restart"),
        )
    )

    assert "committed provider config must not enable live provider" in result.blockers
    assert any("power.force_restart" in blocker for blocker in result.blockers)


def test_redfish_preflight_allows_get_observe_evidence_without_artifact_path(tmp_path) -> None:
    result = run_live_provider_preflight(
        _ready_request(
            tmp_path,
            provider_type="redfish",
            provider_id="redfish-lab",
            credential_ref="prompt://operator/redfish",
            artifact_path=None,
            capabilities=("observe.status", "observe.power_state"),
        )
    )

    assert result.status == PreflightStatus.OK


def test_cli_preflight_blocks_in_test_mode_without_creating_audit_or_approval_files(
    tmp_path,
    capsys,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AGENTICKVM_LAB_PASSWORD", "must-not-read")
    config_path = _write_disabled_pikvm_config(tmp_path)
    audit_path = tmp_path / "audit.sqlite"
    approval_path = tmp_path / "approvals.json"

    exit_code = main(
        [
            "--config",
            str(config_path),
            "--audit-sqlite-path",
            str(audit_path),
            "--approval-path",
            str(approval_path),
            "providers",
            "preflight",
            "--target",
            "pikvm-target",
            "--external-config",
            str(tmp_path / "operator" / "pikvm-live.json"),
            "--artifact-path",
            str(tmp_path / "operator-artifacts"),
            "--live-provider-enabled",
            "--tls-reviewed",
            "--timeout-reviewed",
            "--manual-smoke-acknowledged",
            "--test-mode",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert payload["provider_type"] == "pikvm"
    assert "test mode blocks live provider preflight" in payload["blockers"]
    assert "must-not-read" not in repr(payload)
    assert not audit_path.exists()
    assert not approval_path.exists()


def test_cli_preflight_unknown_target_fails_closed(tmp_path, capsys) -> None:
    config_path = _write_disabled_pikvm_config(tmp_path)

    exit_code = main(
        [
            "--config",
            str(config_path),
            "providers",
            "preflight",
            "--target",
            "missing-target",
            "--external-config",
            str(tmp_path / "operator" / "pikvm-live.json"),
            "--test-mode",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "blocked"
    assert payload["provider_type"] == "unknown"
    assert "unsupported live provider type" in payload["blockers"]
