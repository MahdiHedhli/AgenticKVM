"""Configuration data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from agentickvm.control_plane.decisions import ControlMode, normalize_control_mode
from agentickvm.config.validation import validate_credential_reference
from agentickvm.providers.registry import KNOWN_PROVIDER_TYPES


@dataclass(frozen=True)
class ProviderConfig:
    """Provider config entry."""

    id: str
    type: str
    enabled: bool = True
    description: str | None = None
    credential_ref: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        provider_type = self.type.strip().lower()
        if provider_type not in KNOWN_PROVIDER_TYPES:
            raise ValueError(f"Unknown provider type: {self.type}")
        credential_ref = self.credential_ref
        if credential_ref is not None:
            credential_ref = validate_credential_reference(credential_ref)
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "type", provider_type)
        object.__setattr__(self, "credential_ref", credential_ref)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class TargetConfig:
    """Target config entry."""

    id: str
    provider: str
    enabled: bool = True
    name: str | None = None
    environment: str | None = None
    labels: tuple[str, ...] = ()
    risk_tier: str = "unknown"
    allowed_modes: tuple[ControlMode, ...] = ()
    default_policy: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(self, "provider", self.provider.strip())
        object.__setattr__(self, "labels", tuple(str(label) for label in self.labels))
        object.__setattr__(
            self,
            "allowed_modes",
            tuple(normalize_control_mode(mode) for mode in self.allowed_modes),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class AgenticKVMConfig:
    """Validated AgenticKVM config."""

    version: str
    providers: tuple[ProviderConfig, ...]
    targets: tuple[TargetConfig, ...]
    default_policy_mode: ControlMode = ControlMode.SUPERVISED

    def __post_init__(self) -> None:
        object.__setattr__(self, "default_policy_mode", normalize_control_mode(self.default_policy_mode))


__all__ = [
    "AgenticKVMConfig",
    "ProviderConfig",
    "TargetConfig",
]
