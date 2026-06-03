import inspect
import json

import pytest

from agentickvm.config import ConfigValidationError, load_config
from agentickvm.config import loader as loader_module
from agentickvm.control_plane import (
    ControlMode,
    TargetDefinition,
    TargetRegistry,
    TargetRegistryError,
)
from agentickvm.providers import (
    MockProvider,
    ProviderEntry,
    ProviderRegistry,
    ProviderRegistryError,
)


def _mock_provider_registry() -> ProviderRegistry:
    return ProviderRegistry(
        [ProviderEntry(provider_id="mock", provider_type="mock", provider=MockProvider())]
    )


def test_provider_registry_contract_failures() -> None:
    registry = ProviderRegistry()

    with pytest.raises(ProviderRegistryError, match="Unknown provider id"):
        registry.resolve_enabled("missing")

    with pytest.raises(ProviderRegistryError, match="Unknown provider type"):
        ProviderEntry(provider_id="bad", provider_type="python")

    with pytest.raises(ProviderRegistryError, match="Duplicate provider id"):
        ProviderRegistry(
            [
                ProviderEntry(
                    provider_id="mock",
                    provider_type="mock",
                    provider=MockProvider(),
                ),
                ProviderEntry(
                    provider_id="mock",
                    provider_type="mock",
                    provider=MockProvider(),
                ),
            ]
        )


def test_provider_registry_rejects_disabled_and_placeholder_execution() -> None:
    registry = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                enabled=False,
                provider=MockProvider(),
            ),
            ProviderEntry(
                provider_id="redfish-placeholder",
                provider_type="redfish",
                enabled=False,
            ),
        ]
    )

    with pytest.raises(ProviderRegistryError, match="disabled"):
        registry.resolve_enabled("mock")
    with pytest.raises(ProviderRegistryError, match="disabled"):
        registry.resolve_enabled("redfish-placeholder")


def test_provider_id_normalization_is_stable() -> None:
    entry = ProviderEntry(
        provider_id=" mock ",
        provider_type=" MOCK ",
        provider=MockProvider(),
    )

    assert entry.provider_id == "mock"
    assert entry.provider_type == "mock"


def test_provider_entry_rejects_secret_like_metadata() -> None:
    with pytest.raises(ProviderRegistryError, match="must not contain secrets"):
        ProviderEntry(
            provider_id="mock",
            provider_type="mock",
            provider=MockProvider(),
            metadata={"session_cookie": "do-not-store"},
        )


def test_provider_registry_summary_omits_metadata() -> None:
    registry = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                provider=MockProvider(),
                metadata={"notes": "safe but still not listed"},
            )
        ]
    )

    summary = dict(registry.list_summaries()[0])

    assert summary["id"] == "mock"
    assert "metadata" not in summary


def test_target_registry_contract_failures_and_preserved_fields() -> None:
    target = TargetDefinition(
        target_id="mock-host",
        provider_id="mock",
        labels=("lab", "mock"),
        risk_tier="low",
        allowed_modes=frozenset({ControlMode.OBSERVE}),
    )
    registry = TargetRegistry(provider_registry=_mock_provider_registry(), targets=[target])

    resolved = registry.resolve_enabled("mock-host", mode=ControlMode.OBSERVE)

    assert resolved.labels == ("lab", "mock")
    assert resolved.risk_tier == "low"
    with pytest.raises(TargetRegistryError, match="Unknown target id"):
        registry.resolve_enabled("missing")
    with pytest.raises(TargetRegistryError, match="does not allow mode"):
        registry.resolve_enabled("mock-host", mode=ControlMode.FULL_CONTROL)


def test_target_referencing_disabled_provider_fails_closed() -> None:
    provider_registry = ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                enabled=False,
                provider=MockProvider(),
            )
        ]
    )
    target_registry = TargetRegistry(
        provider_registry=provider_registry,
        targets=[TargetDefinition(target_id="mock-host", provider_id="mock")],
    )

    with pytest.raises(TargetRegistryError, match="non-executable provider"):
        target_registry.resolve_enabled("mock-host")


def test_target_registry_summary_omits_metadata() -> None:
    registry = TargetRegistry(
        provider_registry=_mock_provider_registry(),
        targets=[
            TargetDefinition(
                target_id="mock-host",
                provider_id="mock",
                metadata={"notes": "safe but still not listed"},
            )
        ],
    )

    summary = dict(registry.list_summaries()[0])

    assert summary["id"] == "mock-host"
    assert "metadata" not in summary


def test_target_metadata_rejects_expanded_secret_like_keys() -> None:
    with pytest.raises(TargetRegistryError, match="must not contain secrets"):
        TargetDefinition(
            target_id="mock-host",
            provider_id="mock",
            metadata={"bearer": "do-not-store"},
        )


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "token",
        "api_key",
        "secret",
        "private_key",
        "credential",
        "bearer",
        "session_cookie",
    ],
)
def test_config_loader_rejects_suspicious_keys(tmp_path, key: str) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "mock",
                        "type": "mock",
                        "metadata": {key: "must-not-load"},
                    }
                ],
                "targets": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigValidationError, match="Secret-like config key"):
        load_config(path)


def test_config_loader_cannot_import_arbitrary_provider_classes() -> None:
    source = inspect.getsource(loader_module)

    assert "importlib" not in source
    assert "__import__" not in source


def test_enabled_real_provider_from_config_is_rejected(tmp_path) -> None:
    path = tmp_path / "enabled-real.yaml"
    path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "redfish-lab",
                        "type": "redfish",
                        "enabled": True,
                    }
                ],
                "targets": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not executable"):
        load_config(path)
