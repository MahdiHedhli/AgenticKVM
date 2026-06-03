"""Explicit target registry.

Targets are named scope entries. They are not authority by themselves, but MCP,
CLI, and future APIs must resolve targets through this registry before
constructing capability requests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from agentickvm.control_plane.decisions import ControlMode, normalize_control_mode
from agentickvm.providers.registry import ProviderRegistry

_TARGET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
_SECRET_KEY_FRAGMENTS = frozenset(
    {
        "password",
        "token",
        "api_key",
        "secret",
        "private_key",
        "credential",
        "bearer",
        "session_cookie",
    }
)


class TargetRegistryError(ValueError):
    """Raised when target registry validation fails closed."""


@dataclass(frozen=True)
class TargetDefinition:
    """Configured target entry."""

    target_id: str
    provider_id: str
    enabled: bool = True
    name: str | None = None
    environment: str | None = None
    labels: tuple[str, ...] = ()
    risk_tier: str = "unknown"
    allowed_modes: frozenset[ControlMode] = frozenset()
    default_policy: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        target_id = self.target_id.strip()
        provider_id = self.provider_id.strip()
        if not _TARGET_ID_PATTERN.fullmatch(target_id):
            raise TargetRegistryError(f"Invalid target id: {self.target_id!r}")
        if not provider_id:
            raise TargetRegistryError("Target provider id is required")
        if _contains_secret_key(self.metadata):
            raise TargetRegistryError("Target metadata must not contain secrets")

        allowed_modes = frozenset(normalize_control_mode(mode) for mode in self.allowed_modes)
        labels = tuple(str(label) for label in self.labels)
        object.__setattr__(self, "target_id", target_id)
        object.__setattr__(self, "provider_id", provider_id)
        object.__setattr__(self, "labels", labels)
        object.__setattr__(self, "allowed_modes", allowed_modes)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def allows_mode(self, mode: ControlMode | str) -> bool:
        """Return whether this target allows a visible control mode."""

        if not self.allowed_modes:
            return True
        return normalize_control_mode(mode) in self.allowed_modes


class TargetRegistry:
    """Registry of explicitly configured targets."""

    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        targets: Iterable[TargetDefinition] = (),
    ) -> None:
        self.provider_registry = provider_registry
        self._targets: dict[str, TargetDefinition] = {}
        for target in targets:
            self.register(target)

    def register(self, target: TargetDefinition) -> None:
        """Register one target after validating its provider reference."""

        if target.target_id in self._targets:
            raise TargetRegistryError(f"Duplicate target id: {target.target_id}")
        try:
            self.provider_registry.require(target.provider_id)
        except ValueError as exc:
            raise TargetRegistryError(
                f"Target {target.target_id} references unknown provider "
                f"{target.provider_id}"
            ) from exc
        self._targets[target.target_id] = target

    @property
    def targets(self) -> Mapping[str, TargetDefinition]:
        """Return configured targets."""

        return MappingProxyType(dict(self._targets))

    def list(self) -> tuple[TargetDefinition, ...]:
        """Return configured targets sorted by id."""

        return tuple(self._targets[key] for key in sorted(self._targets))

    def list_summaries(self) -> tuple[Mapping[str, Any], ...]:
        """Return metadata-free target summaries for external interfaces."""

        return tuple(
            MappingProxyType(
                {
                    "id": target.target_id,
                    "provider": target.provider_id,
                    "enabled": target.enabled,
                    "name": target.name,
                    "environment": target.environment,
                    "labels": list(target.labels),
                    "risk_tier": target.risk_tier,
                    "allowed_modes": [mode.value for mode in sorted(target.allowed_modes)],
                }
            )
            for target in self.list()
        )

    def get(self, target_id: str) -> TargetDefinition | None:
        """Return a target entry, or None if unknown."""

        return self._targets.get(target_id)

    def require(self, target_id: str) -> TargetDefinition:
        """Return a target entry or fail closed."""

        target = self.get(target_id)
        if target is None:
            raise TargetRegistryError(f"Unknown target id: {target_id}")
        return target

    def resolve_enabled(
        self,
        target_id: str,
        *,
        mode: ControlMode | str | None = None,
    ) -> TargetDefinition:
        """Return an executable target or fail closed."""

        target = self.require(target_id)
        if not target.enabled:
            raise TargetRegistryError(f"Target is disabled: {target_id}")
        try:
            self.provider_registry.resolve_enabled(target.provider_id)
        except ValueError as exc:
            raise TargetRegistryError(
                f"Target {target_id} references non-executable provider "
                f"{target.provider_id}"
            ) from exc
        if mode is not None:
            self.validate_mode_allowed(target_id, mode)
        return target

    def validate_mode_allowed(
        self,
        target_id: str,
        mode: ControlMode | str,
    ) -> TargetDefinition:
        """Validate a target permits a visible control mode."""

        target = self.require(target_id)
        if not target.allows_mode(mode):
            raise TargetRegistryError(
                f"Target {target_id} does not allow mode "
                f"{normalize_control_mode(mode).value}"
            )
        return target

    def validate_provider_match(
        self,
        target_id: str,
        provider_id: str,
    ) -> TargetDefinition:
        """Validate a requested provider matches the configured target provider."""

        target = self.require(target_id)
        if target.provider_id != provider_id:
            raise TargetRegistryError(
                f"Target {target_id} is configured for provider {target.provider_id}"
            )
        return target


def _contains_secret_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in _SECRET_KEY_FRAGMENTS):
                return True
            if _contains_secret_key(child):
                return True
    elif isinstance(value, (list, tuple, set, frozenset)):
        return any(_contains_secret_key(item) for item in value)
    return False


__all__ = [
    "TargetDefinition",
    "TargetRegistry",
    "TargetRegistryError",
]
