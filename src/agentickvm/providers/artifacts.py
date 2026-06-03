"""Provider artifact safety helpers.

These helpers model screenshot artifact policy. They do not write artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


class ArtifactPolicyError(ValueError):
    """Raised when artifact policy validation fails closed."""


@dataclass(frozen=True)
class ScreenshotArtifactPolicy:
    """Policy for sensitive screenshot artifact metadata."""

    artifact_root: Path
    allow_repo_paths: bool = False
    sensitivity_label: str = "sensitive"

    def __post_init__(self) -> None:
        artifact_root = Path(self.artifact_root)
        if not artifact_root.is_absolute():
            raise ArtifactPolicyError("screenshot artifact root must be explicit")
        object.__setattr__(self, "artifact_root", artifact_root)

    def validate_path(self, *, repo_root: str | Path | None = None) -> None:
        """Validate that the configured artifact root is safe for use."""

        if repo_root is None or self.allow_repo_paths:
            return
        resolved_root = self.artifact_root.resolve()
        resolved_repo = Path(repo_root).resolve()
        if resolved_root == resolved_repo or resolved_root.is_relative_to(resolved_repo):
            raise ArtifactPolicyError(
                "screenshot artifacts must not default into tracked repo paths"
            )

    def metadata(
        self,
        *,
        provider_id: str,
        target_id: str,
        artifact_name: str,
        content_type: str,
        byte_length: int,
    ) -> Mapping[str, Any]:
        """Return safe screenshot artifact metadata without raw image bytes."""

        if byte_length < 0:
            raise ArtifactPolicyError("screenshot artifact byte length cannot be negative")
        if target_id and target_id in artifact_name:
            raise ArtifactPolicyError("screenshot artifact name must not include target id")
        if provider_id and provider_id in artifact_name:
            raise ArtifactPolicyError("screenshot artifact name must not include provider id")

        return MappingProxyType(
            {
                "kind": "screenshot",
                "sensitivity": self.sensitivity_label,
                "artifact_root": str(self.artifact_root),
                "artifact_name": artifact_name,
                "content_type": content_type,
                "byte_length": byte_length,
                "provider_id": provider_id,
                "target_id": "[REDACTED]",
                "raw_bytes_included": False,
            }
        )


__all__ = [
    "ArtifactPolicyError",
    "ScreenshotArtifactPolicy",
]
