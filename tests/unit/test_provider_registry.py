import inspect

import pytest

from agentickvm.providers import (
    MockProvider,
    ProviderEntry,
    ProviderRegistry,
    ProviderRegistryError,
)
from agentickvm.providers import registry as registry_module


def test_mock_provider_registration_resolves_enabled_adapter() -> None:
    provider = MockProvider()
    registry = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                provider=provider,
            )
        ]
    )

    assert registry.require("mock").provider_type == "mock"
    assert registry.resolve_enabled("mock") is provider
    assert registry.list()[0].provider_id == "mock"


def test_mock_only_registry_registers_safe_mock_provider() -> None:
    registry = ProviderRegistry.mock_only()

    provider = registry.resolve_enabled("mock")

    assert isinstance(provider, MockProvider)
    assert provider.is_real_hardware is False


def test_unknown_provider_denied() -> None:
    registry = ProviderRegistry.mock_only()

    with pytest.raises(ProviderRegistryError, match="Unknown provider id"):
        registry.require("redfish-lab")

    with pytest.raises(ProviderRegistryError, match="Unknown provider id"):
        registry.resolve_enabled("redfish-lab")


def test_duplicate_provider_rejected() -> None:
    first = ProviderEntry(provider_id="mock", provider_type="mock", provider=MockProvider())
    second = ProviderEntry(provider_id="mock", provider_type="mock", provider=MockProvider())

    with pytest.raises(ProviderRegistryError, match="Duplicate provider id"):
        ProviderRegistry([first, second])


def test_disabled_provider_cannot_execute() -> None:
    registry = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                enabled=False,
                provider=MockProvider(),
            )
        ]
    )

    with pytest.raises(ProviderRegistryError, match="disabled"):
        registry.resolve_enabled("mock")


def test_registry_does_not_import_arbitrary_classes_from_config() -> None:
    source = inspect.getsource(registry_module)

    assert "importlib" not in source
    assert "__import__" not in source
    with pytest.raises(ProviderRegistryError, match="Unknown provider type"):
        ProviderEntry(
            provider_id="evil",
            provider_type="agentickvm.providers.mock.MockProvider",
            enabled=False,
        )


def test_real_provider_placeholder_is_not_executable_by_default() -> None:
    registry = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="redfish-lab",
                provider_type="redfish",
                enabled=False,
                description="Disabled placeholder only",
            )
        ]
    )

    assert registry.require("redfish-lab").provider is None
    with pytest.raises(ProviderRegistryError, match="disabled"):
        registry.resolve_enabled("redfish-lab")


def test_enabled_real_provider_placeholder_rejected() -> None:
    with pytest.raises(ProviderRegistryError, match="not executable"):
        ProviderEntry(provider_id="redfish-lab", provider_type="redfish", enabled=True)


def test_provider_id_and_type_must_match_adapter() -> None:
    with pytest.raises(ProviderRegistryError, match="id does not match"):
        ProviderEntry(provider_id="other", provider_type="mock", provider=MockProvider())

    provider = MockProvider()
    with pytest.raises(ProviderRegistryError, match="type does not match"):
        ProviderEntry(
            provider_id=provider.provider_id,
            provider_type="redfish",
            enabled=False,
            provider=provider,
        )
