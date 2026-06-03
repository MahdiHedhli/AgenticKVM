"""Safe configuration loader.

The bootstrap examples are JSON-compatible YAML and are parsed with the Python
standard library. Full YAML support is intentionally deferred until dependency
choices and threat-model requirements are explicit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from agentickvm.config.models import (
    AgenticKVMConfig,
    ProviderConfig,
    TargetConfig,
)
from agentickvm.config.validation import (
    ConfigValidationError,
    reject_unsafe_config_keys,
)
from agentickvm.control_plane import (
    CapabilityPolicy,
    InMemoryAuditSink,
    TargetDefinition,
    TargetRegistry,
    mode_preset,
)
from agentickvm.providers import (
    MockProvider,
    ProviderEntry,
    ProviderRegistry,
)


@dataclass(frozen=True)
class ConfigRuntime:
    """Runtime objects built from safe config."""

    config: AgenticKVMConfig
    provider_registry: ProviderRegistry
    target_registry: TargetRegistry
    policy: CapabilityPolicy
    audit_sink: InMemoryAuditSink


def mock_only_config() -> AgenticKVMConfig:
    """Return the safe built-in mock-only config."""

    return AgenticKVMConfig(
        version="0.1",
        providers=(
            ProviderConfig(
                id="mock",
                type="mock",
                enabled=True,
                description="Safe in-memory mock provider",
            ),
        ),
        targets=(
            TargetConfig(
                id="mock-host",
                provider="mock",
                enabled=True,
                name="Mock Host",
                environment="local",
                labels=("mock", "safe"),
                risk_tier="low",
                allowed_modes=("Observe", "Supervised", "Full Control"),
                metadata={"description": "safe mock target"},
            ),
        ),
        default_policy_mode="Supervised",
    )


def load_config(path: str | Path | None = None) -> AgenticKVMConfig:
    """Load config from an explicit repo-local path or safe built-in mock config."""

    if path is None:
        return mock_only_config()

    config_path = Path(path)
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ConfigValidationError("Config file must contain an object")
    return config_from_mapping(raw)


def config_from_mapping(raw: Mapping[str, Any]) -> AgenticKVMConfig:
    """Build a config model from a parsed mapping."""

    reject_unsafe_config_keys(raw)

    provider_items = raw.get("providers")
    target_items = raw.get("targets")
    if not isinstance(provider_items, list):
        raise ConfigValidationError("Config providers must be a list")
    if not isinstance(target_items, list):
        raise ConfigValidationError("Config targets must be a list")

    providers = tuple(_provider_config(item) for item in provider_items)
    targets = tuple(_target_config(item) for item in target_items)
    default_policy = raw.get("default_policy", {})
    if default_policy is None:
        default_policy = {}
    if not isinstance(default_policy, Mapping):
        raise ConfigValidationError("default_policy must be an object")

    config = AgenticKVMConfig(
        version=str(raw.get("version", "0.1")),
        providers=providers,
        targets=targets,
        default_policy_mode=str(default_policy.get("mode", "Supervised")),
    )
    build_provider_registry(config)
    build_target_registry(config, build_provider_registry(config))
    return config


def build_runtime(
    config: AgenticKVMConfig | None = None,
    *,
    audit_sink: InMemoryAuditSink | None = None,
) -> ConfigRuntime:
    """Build safe runtime objects from config."""

    resolved_config = config or mock_only_config()
    provider_registry = build_provider_registry(resolved_config)
    target_registry = build_target_registry(resolved_config, provider_registry)
    policy = mode_preset(resolved_config.default_policy_mode)
    return ConfigRuntime(
        config=resolved_config,
        provider_registry=provider_registry,
        target_registry=target_registry,
        policy=policy,
        audit_sink=audit_sink or InMemoryAuditSink(),
    )


def build_provider_registry(config: AgenticKVMConfig) -> ProviderRegistry:
    """Build an explicit provider registry from config."""

    entries: list[ProviderEntry] = []
    for provider in config.providers:
        adapter = None
        if provider.enabled and provider.type == "mock":
            adapter = MockProvider()
        entries.append(
            ProviderEntry(
                provider_id=provider.id,
                provider_type=provider.type,
                enabled=provider.enabled,
                provider=adapter,
                description=provider.description,
                metadata=provider.metadata,
            )
        )
    return ProviderRegistry(entries)


def build_target_registry(
    config: AgenticKVMConfig,
    provider_registry: ProviderRegistry,
) -> TargetRegistry:
    """Build an explicit target registry from config."""

    targets = [
        TargetDefinition(
            target_id=target.id,
            provider_id=target.provider,
            enabled=target.enabled,
            name=target.name,
            environment=target.environment,
            labels=target.labels,
            risk_tier=target.risk_tier,
            allowed_modes=frozenset(target.allowed_modes),
            default_policy=target.default_policy,
            metadata=target.metadata,
        )
        for target in config.targets
    ]
    return TargetRegistry(provider_registry=provider_registry, targets=targets)


def _provider_config(item: Any) -> ProviderConfig:
    if not isinstance(item, Mapping):
        raise ConfigValidationError("Provider entries must be objects")
    return ProviderConfig(
        id=_required_str(item, "id"),
        type=_required_str(item, "type"),
        enabled=bool(item.get("enabled", True)),
        description=item.get("description"),
        metadata=_mapping(item.get("metadata", {}), "provider metadata"),
    )


def _target_config(item: Any) -> TargetConfig:
    if not isinstance(item, Mapping):
        raise ConfigValidationError("Target entries must be objects")
    return TargetConfig(
        id=_required_str(item, "id"),
        provider=_required_str(item, "provider"),
        enabled=bool(item.get("enabled", True)),
        name=item.get("name"),
        environment=item.get("environment"),
        labels=tuple(item.get("labels", ())),
        risk_tier=str(item.get("risk_tier", "unknown")),
        allowed_modes=tuple(item.get("allowed_modes", ())),
        default_policy=item.get("default_policy"),
        metadata=_mapping(item.get("metadata", {}), "target metadata"),
    )


def _required_str(item: Mapping[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f"Missing required string: {key}")
    return value


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigValidationError(f"{name} must be an object")
    return value


__all__ = [
    "ConfigRuntime",
    "build_provider_registry",
    "build_runtime",
    "build_target_registry",
    "config_from_mapping",
    "load_config",
    "mock_only_config",
]
