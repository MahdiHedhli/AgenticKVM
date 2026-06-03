"""Safe repo-local configuration loading."""

from agentickvm.config.loader import (
    ConfigRuntime,
    build_provider_registry,
    build_runtime,
    build_target_registry,
    config_from_mapping,
    load_config,
    mock_only_config,
)
from agentickvm.config.models import (
    AgenticKVMConfig,
    ProviderConfig,
    TargetConfig,
)
from agentickvm.config.validation import (
    ALLOWED_CREDENTIAL_REF_SCHEMES,
    ConfigValidationError,
    reject_unsafe_config_keys,
    validate_credential_reference,
)

__all__ = [
    "AgenticKVMConfig",
    "ALLOWED_CREDENTIAL_REF_SCHEMES",
    "ConfigRuntime",
    "ConfigValidationError",
    "ProviderConfig",
    "TargetConfig",
    "build_provider_registry",
    "build_runtime",
    "build_target_registry",
    "config_from_mapping",
    "load_config",
    "mock_only_config",
    "reject_unsafe_config_keys",
    "validate_credential_reference",
]
