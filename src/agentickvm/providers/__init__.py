"""Provider interfaces for AgenticKVM."""

from agentickvm.providers.base import (
    Provider,
    ProviderActionRequest,
    ProviderActionResult,
)
from agentickvm.providers.mock import MockProvider

__all__ = [
    "MockProvider",
    "Provider",
    "ProviderActionRequest",
    "ProviderActionResult",
]
