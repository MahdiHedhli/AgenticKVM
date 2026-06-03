"""Provider interfaces for AgenticKVM."""

from agentickvm.providers.base import (
    Provider,
    ProviderActionRequest,
    ProviderActionResult,
    ProviderStatus,
    ProviderValidationResult,
)
from agentickvm.providers.mock import MockProvider
from agentickvm.providers.placeholders import (
    DisabledRealProviderPlaceholder,
    OBSERVE_ONLY_REAL_PROVIDER_CAPABILITIES,
    PiKVMProviderPlaceholder,
    RealProviderNotEnabledError,
    RedfishProviderPlaceholder,
)
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
    "DisabledRealProviderPlaceholder",
    "KNOWN_PROVIDER_TYPES",
    "MockProvider",
    "OBSERVE_ONLY_REAL_PROVIDER_CAPABILITIES",
    "PLACEHOLDER_PROVIDER_TYPES",
    "PiKVMProviderPlaceholder",
    "Provider",
    "ProviderActionRequest",
    "ProviderActionResult",
    "ProviderEntry",
    "ProviderRegistry",
    "ProviderRegistryError",
    "ProviderStatus",
    "ProviderValidationResult",
    "RealProviderNotEnabledError",
    "RedfishProviderPlaceholder",
]
