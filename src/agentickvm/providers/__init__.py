"""Provider interfaces for AgenticKVM."""

from agentickvm.providers.base import (
    Provider,
    ProviderActionRequest,
    ProviderActionResult,
)
from agentickvm.providers.mock import MockProvider
from agentickvm.providers.registry import (
    EXECUTABLE_PROVIDER_TYPES,
    KNOWN_PROVIDER_TYPES,
    PLACEHOLDER_PROVIDER_TYPES,
    ProviderEntry,
    ProviderRegistry,
    ProviderRegistryError,
)

__all__ = [
    "EXECUTABLE_PROVIDER_TYPES",
    "KNOWN_PROVIDER_TYPES",
    "MockProvider",
    "PLACEHOLDER_PROVIDER_TYPES",
    "Provider",
    "ProviderActionRequest",
    "ProviderActionResult",
    "ProviderEntry",
    "ProviderRegistry",
    "ProviderRegistryError",
]
