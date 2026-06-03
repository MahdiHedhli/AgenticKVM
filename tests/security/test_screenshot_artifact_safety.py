import json
from pathlib import Path

import pytest

from agentickvm.control_plane import (
    Actor,
    ActorType,
    AuditEventType,
    CapabilityRef,
    LocalJSONLAuditSink,
    PolicyDecision,
    build_audit_event,
)
from agentickvm.providers.artifacts import (
    ArtifactPolicyError,
    ScreenshotArtifactPolicy,
)

ROOT = Path(__file__).resolve().parents[2]


def test_screenshot_artifact_policy_accepts_explicit_temp_path(tmp_path) -> None:
    policy = ScreenshotArtifactPolicy(artifact_root=tmp_path / "artifacts")

    policy.validate_path(repo_root=ROOT)
    metadata = policy.metadata(
        provider_id="pikvm-fixture",
        target_id="pikvm-fixture-target",
        artifact_name="screenshot-fixture-0001.png",
        content_type="image/png",
        byte_length=128,
    )

    assert metadata["target_id"] == "[REDACTED]"
    assert metadata["raw_bytes_included"] is False
    assert "pikvm-fixture-target" not in metadata["artifact_name"]


def test_screenshot_artifact_policy_rejects_repo_paths_by_default() -> None:
    policy = ScreenshotArtifactPolicy(artifact_root=ROOT / "artifacts")

    with pytest.raises(ArtifactPolicyError, match="tracked repo paths"):
        policy.validate_path(repo_root=ROOT)


def test_screenshot_artifact_name_cannot_leak_target_or_provider() -> None:
    policy = ScreenshotArtifactPolicy(artifact_root=Path("/tmp/agentickvm-artifacts"))

    with pytest.raises(ArtifactPolicyError, match="target id"):
        policy.metadata(
            provider_id="pikvm-fixture",
            target_id="pikvm-fixture-target",
            artifact_name="pikvm-fixture-target-screen.png",
            content_type="image/png",
            byte_length=128,
        )
    with pytest.raises(ArtifactPolicyError, match="provider id"):
        policy.metadata(
            provider_id="pikvm-fixture",
            target_id="target-a",
            artifact_name="pikvm-fixture-screen.png",
            content_type="image/png",
            byte_length=128,
        )


def test_audit_event_contains_screenshot_metadata_only(tmp_path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    policy = ScreenshotArtifactPolicy(artifact_root=tmp_path / "artifacts")
    metadata = dict(
        policy.metadata(
            provider_id="pikvm-fixture",
            target_id="pikvm-fixture-target",
            artifact_name="screenshot-fixture-0001.png",
            content_type="image/png",
            byte_length=128,
        )
    )
    event = build_audit_event(
        event_type=AuditEventType.RESULT_RETURNED,
        correlation_id="corr-screenshot",
        session_id="s1",
        actor=Actor(type=ActorType.AGENT, id="agent-1"),
        capability=CapabilityRef(
            id="observe.screenshot",
            family="observe",
            action="screenshot",
        ),
        policy_decision=PolicyDecision.ALLOW,
        result={
            "artifact": metadata,
            "raw_image": b"synthetic-image-bytes",
            "screenshot_bytes": b"synthetic-image-bytes",
        },
    )

    LocalJSONLAuditSink(audit_path).emit(event)
    record = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    audit_result = record["event"]["result"]

    assert audit_result["artifact"]["raw_bytes_included"] is False
    assert audit_result["raw_image"] == "[REDACTED]"
    assert audit_result["screenshot_bytes"] == "[REDACTED]"
    assert "synthetic-image-bytes" not in repr(record)


def test_synthetic_screenshot_fixture_is_metadata_only() -> None:
    fixture = json.loads(
        (
            ROOT
            / "tests"
            / "fixtures"
            / "providers"
            / "pikvm"
            / "screenshot-metadata.json"
        ).read_text(encoding="utf-8")
    )

    assert fixture["raw_bytes_included"] is False
    assert fixture["artifact"]["storage"] == "metadata-only"
    assert "raw_image" not in repr(fixture)
    assert "screenshot_bytes" not in repr(fixture)


def test_gitignore_blocks_common_screenshot_artifact_outputs() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "artifacts/" in gitignore
    assert "agentickvm-artifacts/" in gitignore
    assert "screenshots/" in gitignore
    assert "*.screenshot.png" in gitignore
