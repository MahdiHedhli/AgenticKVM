"""Audit retention and rotation policy model.

This module defines validation rules only. It does not delete, rotate, archive,
or write audit logs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from agentickvm.control_plane.audit import redact_mapping


class AuditRetentionPolicyError(ValueError):
    """Raised when retention policy validation fails closed."""


@dataclass(frozen=True)
class AuditRotationDecision:
    """Rotation eligibility result."""

    ok: bool
    reason: str
    policy_id: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe decision payload."""

        return {
            "ok": self.ok,
            "reason": self.reason,
            "policy_id": self.policy_id,
        }


@dataclass(frozen=True)
class AuditRetentionPolicy:
    """Policy for future audit retention and rotation."""

    policy_id: str
    max_event_count: int | None = None
    max_log_bytes: int | None = None
    max_age_days: int | None = None
    rotation_requires_checkpoint: bool = True
    rotation_requires_verified_archive: bool = True
    allow_silent_deletion: bool = False
    archive_metadata: Mapping[str, Any] = field(default_factory=dict)
    redactions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.policy_id:
            raise AuditRetentionPolicyError("policy_id is required")
        for field_name in ("max_event_count", "max_log_bytes", "max_age_days"):
            value = getattr(self, field_name)
            if value is not None and value <= 0:
                raise AuditRetentionPolicyError(f"{field_name} must be positive")
        if self.allow_silent_deletion:
            raise AuditRetentionPolicyError("silent audit deletion is not allowed")
        if not self.rotation_requires_checkpoint and not self.rotation_requires_verified_archive:
            raise AuditRetentionPolicyError(
                "rotation requires checkpoint or verified archive"
            )
        safe_metadata, redactions = redact_mapping(dict(self.archive_metadata))
        object.__setattr__(
            self,
            "archive_metadata",
            MappingProxyType(dict(safe_metadata)),
        )
        object.__setattr__(
            self,
            "redactions",
            tuple(self.redactions)
            + tuple(f"archive_metadata.{path}" for path in redactions),
        )

    def rotation_decision(
        self,
        *,
        checkpoint_verified: bool,
        archive_verified: bool,
    ) -> AuditRotationDecision:
        """Return whether rotation is allowed under this policy."""

        if self.rotation_requires_checkpoint and not checkpoint_verified:
            return AuditRotationDecision(
                ok=False,
                reason="rotation requires verified checkpoint",
                policy_id=self.policy_id,
            )
        if self.rotation_requires_verified_archive and not archive_verified:
            return AuditRotationDecision(
                ok=False,
                reason="rotation requires verified archive",
                policy_id=self.policy_id,
            )
        return AuditRotationDecision(
            ok=True,
            reason="rotation allowed after verification",
            policy_id=self.policy_id,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe policy payload."""

        return json.loads(
            json.dumps(
                {
                    "policy_id": self.policy_id,
                    "max_event_count": self.max_event_count,
                    "max_log_bytes": self.max_log_bytes,
                    "max_age_days": self.max_age_days,
                    "rotation_requires_checkpoint": self.rotation_requires_checkpoint,
                    "rotation_requires_verified_archive": (
                        self.rotation_requires_verified_archive
                    ),
                    "allow_silent_deletion": self.allow_silent_deletion,
                    "archive_metadata": dict(self.archive_metadata),
                    "redactions": sorted(set(self.redactions)),
                },
                sort_keys=True,
            )
        )


__all__ = [
    "AuditRetentionPolicy",
    "AuditRetentionPolicyError",
    "AuditRotationDecision",
]
