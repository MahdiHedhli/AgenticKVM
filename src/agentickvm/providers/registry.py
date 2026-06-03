"""Explicit provider registry.

Providers are execution adapters only. External interfaces must resolve a
configured provider through this registry before `ControlPlane` can receive a
provider instance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from agentickvm.providers.base import Provider

EXECUTABLE_PROVIDER_TYPES = frozenset({"mock"})
TEST_FIXTURE_PROVIDER_RISK_CLASS = "test_fake_observe_only"
PLACEHOLDER_PROVIDER_TYPES = frozenset(
    {
        "pikvm",
        "redfish",
        "ilo",
        "idrac",
        "ipmi",
        "supermicro",
        "proxmox",
    }
)
KNOWN_PROVIDER_TYPES = EXECUTABLE_PROVIDER_TYPES | PLACEHOLDER_PROVIDER_TYPES

_PROVIDER_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
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


class ProviderRegistryError(ValueError):
    """Raised when provider registry validation fails closed."""


@dataclass(frozen=True)
class ProviderEntry:
    """Configured provider entry.

    A provider can be configured without an adapter only when it is disabled.
    That supports real-provider placeholders without creating execution paths.
    """

    provider_id: str
    provider_type: str
    enabled: bool = True
    provider: Provider | None = None
    description: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        provider_id = self.provider_id.strip()
        provider_type = self.provider_type.strip().lower()
        if not _PROVIDER_ID_PATTERN.fullmatch(provider_id):
            raise ProviderRegistryError(f"Invalid provider id: {self.provider_id!r}")
        if provider_type not in KNOWN_PROVIDER_TYPES:
            raise ProviderRegistryError(f"Unknown provider type: {self.provider_type}")
        if _contains_secret_key(self.metadata):
            raise ProviderRegistryError("Provider metadata must not contain secrets")
        if (
            self.enabled
            and provider_type not in EXECUTABLE_PROVIDER_TYPES
            and not _is_test_fixture_adapter(self.provider, provider_type)
        ):
            raise ProviderRegistryError(
                f"Provider type {provider_type} is not executable in this lane"
            )
        if self.enabled and self.provider is None:
            raise ProviderRegistryError("Enabled providers require an adapter instance")
        if self.provider is not None:
            if self.provider.provider_id != provider_id:
                raise ProviderRegistryError(
                    "Provider adapter id does not match configured provider id"
                )
            if self.provider.provider_kind != provider_type:
                raise ProviderRegistryError(
                    "Provider adapter type does not match configured provider type"
                )
            if (
                provider_type not in EXECUTABLE_PROVIDER_TYPES
                and not _is_test_fixture_adapter(self.provider, provider_type)
            ):
                raise ProviderRegistryError(
                    f"Provider type {provider_type} is not executable in this lane"
                )

        object.__setattr__(self, "provider_id", provider_id)
        object.__setattr__(self, "provider_type", provider_type)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


class ProviderRegistry:
    """Registry of explicitly configured providers."""

    def __init__(self, providers: Iterable[ProviderEntry] = ()) -> None:
        self._providers: dict[str, ProviderEntry] = {}
        for provider in providers:
            self.register(provider)

    @classmethod
    def mock_only(cls, *, provider_id: str = "mock") -> ProviderRegistry:
        """Return a registry with one enabled safe mock provider."""

        from agentickvm.providers.mock import MockProvider

        return cls(
            [
                ProviderEntry(
                    provider_id=provider_id,
                    provider_type="mock",
                    enabled=True,
                    provider=MockProvider(),
                    description="Safe in-memory mock provider",
                )
            ]
        )

    def register(self, provider: ProviderEntry) -> None:
        """Register one explicit provider entry."""

        if provider.provider_id in self._providers:
            raise ProviderRegistryError(f"Duplicate provider id: {provider.provider_id}")
        self._providers[provider.provider_id] = provider

    @property
    def providers(self) -> Mapping[str, ProviderEntry]:
        """Return configured providers."""

        return MappingProxyType(dict(self._providers))

    def list(self) -> tuple[ProviderEntry, ...]:
        """Return configured providers sorted by id."""

        return tuple(self._providers[key] for key in sorted(self._providers))

    def list_summaries(self) -> tuple[Mapping[str, Any], ...]:
        """Return metadata-free provider summaries for external interfaces."""

        return tuple(
            MappingProxyType(
                {
                    "id": provider.provider_id,
                    "type": provider.provider_type,
                    "enabled": provider.enabled,
                    "executable": _is_executable_entry(provider),
                    "description": provider.description,
                }
            )
            for provider in self.list()
        )

    def get(self, provider_id: str) -> ProviderEntry | None:
        """Return a provider entry, or None if unknown."""

        return self._providers.get(provider_id)

    def require(self, provider_id: str) -> ProviderEntry:
        """Return a provider entry or fail closed."""

        provider = self.get(provider_id)
        if provider is None:
            raise ProviderRegistryError(f"Unknown provider id: {provider_id}")
        return provider

    def validate_provider_type(self, provider_id: str, provider_type: str) -> ProviderEntry:
        """Validate a provider exists and has the expected explicit type."""

        provider = self.require(provider_id)
        if provider.provider_type != provider_type.strip().lower():
            raise ProviderRegistryError(
                f"Provider {provider_id} is not type {provider_type}"
            )
        return provider

    def resolve_enabled(self, provider_id: str) -> Provider:
        """Return an executable provider adapter or fail closed."""

        provider = self.require(provider_id)
        if not provider.enabled:
            raise ProviderRegistryError(f"Provider is disabled: {provider_id}")
        if not _is_executable_entry(provider):
            raise ProviderRegistryError(
                f"Provider type {provider.provider_type} is not executable"
            )
        if provider.provider is None:
            raise ProviderRegistryError(f"Provider has no executable adapter: {provider_id}")
        return provider.provider


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


def _is_test_fixture_adapter(provider: Provider | None, provider_type: str) -> bool:
    if provider is None:
        return False
    return (
        provider.provider_kind == provider_type
        and provider.enabled
        and provider.is_real_hardware is False
        and provider.risk_class == TEST_FIXTURE_PROVIDER_RISK_CLASS
    )


def _is_executable_entry(provider: ProviderEntry) -> bool:
    if not provider.enabled or provider.provider is None:
        return False
    if provider.provider_type in EXECUTABLE_PROVIDER_TYPES:
        return True
    return _is_test_fixture_adapter(provider.provider, provider.provider_type)


__all__ = [
    "EXECUTABLE_PROVIDER_TYPES",
    "KNOWN_PROVIDER_TYPES",
    "PLACEHOLDER_PROVIDER_TYPES",
    "ProviderEntry",
    "ProviderRegistry",
    "ProviderRegistryError",
    "TEST_FIXTURE_PROVIDER_RISK_CLASS",
]
