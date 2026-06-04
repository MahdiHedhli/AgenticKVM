import json

import pytest

from agentickvm.control_plane import (
    AuditRetentionPolicy,
    AuditRetentionPolicyError,
)


def test_retention_policy_validates_and_serializes() -> None:
    policy = AuditRetentionPolicy(
        policy_id="local-retention",
        max_event_count=1000,
        max_log_bytes=1_000_000,
        max_age_days=30,
        archive_metadata={"storage": "local-test"},
    )
    payload = policy.to_dict()

    assert payload["policy_id"] == "local-retention"
    assert payload["rotation_requires_checkpoint"] is True
    assert payload["rotation_requires_verified_archive"] is True
    assert json.loads(json.dumps(payload, sort_keys=True)) == payload


def test_retention_policy_rejects_silent_deletion_and_unverified_rotation() -> None:
    with pytest.raises(AuditRetentionPolicyError, match="silent audit deletion"):
        AuditRetentionPolicy(policy_id="bad", allow_silent_deletion=True)

    with pytest.raises(AuditRetentionPolicyError, match="checkpoint or verified archive"):
        AuditRetentionPolicy(
            policy_id="bad",
            rotation_requires_checkpoint=False,
            rotation_requires_verified_archive=False,
        )


def test_rotation_decision_requires_checkpoint_and_archive() -> None:
    policy = AuditRetentionPolicy(policy_id="rotate")

    missing_checkpoint = policy.rotation_decision(
        checkpoint_verified=False,
        archive_verified=True,
    )
    missing_archive = policy.rotation_decision(
        checkpoint_verified=True,
        archive_verified=False,
    )
    allowed = policy.rotation_decision(
        checkpoint_verified=True,
        archive_verified=True,
    )

    assert missing_checkpoint.ok is False
    assert missing_checkpoint.reason == "rotation requires verified checkpoint"
    assert missing_archive.ok is False
    assert missing_archive.reason == "rotation requires verified archive"
    assert allowed.ok is True


def test_retention_policy_redacts_archive_metadata() -> None:
    policy = AuditRetentionPolicy(
        policy_id="redacted",
        archive_metadata={
            "credential_ref": "vault://prod/not-for-tests",
            "nested": {"token": "must-not-leak"},
            "safe": "ok",
        },
    )
    encoded = json.dumps(policy.to_dict(), sort_keys=True)

    assert "vault://prod" not in encoded
    assert "must-not-leak" not in encoded
    assert "[REDACTED]" in encoded
    assert "archive_metadata.credential_ref" in policy.redactions
