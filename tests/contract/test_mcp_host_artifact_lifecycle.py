import json
from pathlib import Path

from agentickvm.control_plane import verify_audit_chain
from agentickvm.mcp_sdk import MCPHostCompatibilityLayer
from agentickvm.providers.artifacts import ScreenshotArtifactPolicy

ROOT = Path(__file__).resolve().parents[2]
PIKVM_FIXTURE_CONFIG = ROOT / "examples" / "config" / "pikvm-observe-fixture.yaml"
EXPECTED_METADATA = json.loads(
    (
        ROOT
        / "tests"
        / "fixtures"
        / "artifacts"
        / "pikvm-host-screenshot-metadata.json"
    ).read_text(encoding="utf-8")
)


def _records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _observe_pikvm_screen(host: MCPHostCompatibilityLayer):
    return host.call_tool(
        {
            "tool_name": "observe_screen",
            "target": "pikvm-fixture-target",
            "provider": "pikvm-fixture",
            "session_id": "host-artifact-s1",
            "requester_id": "host-artifact-test",
            "correlation_id": "host-artifact-observe-screen",
        }
    )


def test_pikvm_fixture_screen_artifact_is_metadata_only_at_host_boundary(tmp_path) -> None:
    audit_path = tmp_path / "host-artifact.jsonl"
    host = MCPHostCompatibilityLayer.from_config(
        str(PIKVM_FIXTURE_CONFIG),
        audit_path=audit_path,
    )

    result = _observe_pikvm_screen(host)
    screenshot = result["data"]["provider_result"]["data"]["screenshot"]

    assert result["status"] == "ok"
    assert screenshot["raw_bytes_included"] is False
    assert screenshot["artifact"] == EXPECTED_METADATA
    assert screenshot["artifact"]["sensitivity"] == "sensitive"
    assert "pikvm-fixture-target" not in screenshot["artifact"]["artifact_name"]
    assert "pikvm-fixture" not in screenshot["artifact"]["artifact_name"]
    assert "screenshot_bytes" not in repr(result)
    assert "raw_image" not in repr(result)


def test_pikvm_fixture_artifact_audit_records_metadata_only(tmp_path) -> None:
    audit_path = tmp_path / "host-artifact-audit.jsonl"
    host = MCPHostCompatibilityLayer.from_config(
        str(PIKVM_FIXTURE_CONFIG),
        audit_path=audit_path,
    )

    result = _observe_pikvm_screen(host)
    content = audit_path.read_text(encoding="utf-8")
    records = _records(audit_path)
    serialized_records = json.dumps(records, sort_keys=True)

    assert result["status"] == "ok"
    assert "provider_execution_completed" in [
        record["event"]["event_type"] for record in records
    ]
    assert '"sensitivity": "sensitive"' in serialized_records
    assert '"raw_bytes_included": false' in serialized_records
    assert "screenshot_bytes" not in content
    assert "raw_image" not in content
    assert "synthetic-image-bytes" not in content
    assert verify_audit_chain(audit_path) is True


def test_host_artifact_lifecycle_uses_temp_paths_without_writing_artifacts(
    tmp_path,
) -> None:
    audit_path = tmp_path / "audit" / "host-artifact-path.jsonl"
    artifact_root = tmp_path / "host-artifacts"
    policy = ScreenshotArtifactPolicy(artifact_root=artifact_root)
    policy.validate_path(repo_root=ROOT)
    host = MCPHostCompatibilityLayer.from_config(
        str(PIKVM_FIXTURE_CONFIG),
        audit_path=audit_path,
    )

    result = _observe_pikvm_screen(host)
    metadata = policy.metadata(
        provider_id="pikvm-fixture",
        target_id="pikvm-fixture-target",
        artifact_name="screenshot-fixture-0001.png",
        content_type="image/png",
        byte_length=128,
    )

    assert result["status"] == "ok"
    assert str(metadata["artifact_root"]).startswith(str(tmp_path))
    assert not str(metadata["artifact_root"]).startswith(str(ROOT))
    assert metadata["raw_bytes_included"] is False
    assert sorted(path.name for path in tmp_path.iterdir()) == ["audit"]
    assert not artifact_root.exists()
    assert verify_audit_chain(audit_path) is True


def test_host_artifact_fixture_contains_no_real_hosts_or_secrets() -> None:
    fixture_text = (
        ROOT
        / "tests"
        / "fixtures"
        / "artifacts"
        / "pikvm-host-screenshot-metadata.json"
    ).read_text(encoding="utf-8")

    assert "password" not in fixture_text.lower()
    assert "token" not in fixture_text.lower()
    assert "secret" not in fixture_text.lower()
    assert "192.168." not in fixture_text
    assert "10.0." not in fixture_text
    assert "172.16." not in fixture_text
