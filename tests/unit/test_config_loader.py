import json
from pathlib import Path

import pytest

from agentickvm.config import (
    ConfigValidationError,
    build_provider_registry,
    build_runtime,
    build_target_registry,
    load_config,
    mock_only_config,
)
from agentickvm.providers import ProviderRegistryError
from agentickvm.providers.pikvm import PiKVMObserveProvider
from agentickvm.providers.redfish import RedfishObserveProvider

ROOT = Path(__file__).resolve().parents[2]


def test_load_mock_only_config_builds_mock_registries() -> None:
    config = load_config(ROOT / "examples" / "config" / "mock-only.yaml")
    runtime = build_runtime(config)

    provider = runtime.provider_registry.resolve_enabled("mock")
    target = runtime.target_registry.resolve_enabled("mock-host")

    assert provider.provider_id == "mock"
    assert provider.is_real_hardware is False
    assert target.provider_id == "mock"
    assert runtime.policy.mode.value == "Supervised"


def test_default_config_is_builtin_mock_only_and_not_global(monkeypatch) -> None:
    monkeypatch.setenv("AGENTICKVM_TOKEN", "must-not-be-read")
    monkeypatch.setenv("HOME", "/nonexistent-agentickvm-home")

    config = load_config()
    runtime = build_runtime(config)

    assert config == mock_only_config()
    assert runtime.provider_registry.resolve_enabled("mock").is_real_hardware is False
    assert runtime.target_registry.resolve_enabled("mock-host").target_id == "mock-host"


def test_unknown_provider_type_rejected(tmp_path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text(
        json.dumps(
            {
                "providers": [{"id": "evil", "type": "python_class"}],
                "targets": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown provider type"):
        load_config(path)


def test_target_with_unknown_provider_rejected(tmp_path) -> None:
    path = tmp_path / "bad-target.yaml"
    path.write_text(
        json.dumps(
            {
                "providers": [{"id": "mock", "type": "mock"}],
                "targets": [{"id": "bad-host", "provider": "missing"}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown provider"):
        load_config(path)


def test_disabled_provider_cannot_execute_from_config() -> None:
    config = load_config(ROOT / "examples" / "config" / "provider-placeholders.yaml")
    provider_registry = build_provider_registry(config)

    with pytest.raises(ProviderRegistryError, match="disabled"):
        provider_registry.resolve_enabled("redfish-placeholder")


def test_disabled_target_cannot_execute_from_config() -> None:
    config = load_config(ROOT / "examples" / "config" / "provider-placeholders.yaml")
    provider_registry = build_provider_registry(config)
    target_registry = build_target_registry(config, provider_registry)

    with pytest.raises(ValueError, match="disabled"):
        target_registry.resolve_enabled("disabled-pikvm-target")


def test_invalid_config_fails_closed(tmp_path) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

    with pytest.raises(ConfigValidationError, match="object"):
        load_config(path)


@pytest.mark.parametrize(
    ("filename", "provider_id", "target_id"),
    [
        (
            "pikvm-observe-placeholder.yaml",
            "pikvm-observe-placeholder",
            "pikvm-observe-target",
        ),
        (
            "redfish-observe-placeholder.yaml",
            "redfish-observe-placeholder",
            "redfish-observe-target",
        ),
        (
            "lab-observe-only.example.yaml",
            "pikvm-lab-placeholder",
            "pikvm-lab-observe",
        ),
    ],
)
def test_observe_only_provider_placeholder_configs_load_disabled(
    filename: str,
    provider_id: str,
    target_id: str,
) -> None:
    config = load_config(ROOT / "examples" / "config" / filename)
    runtime = build_runtime(config)

    provider_entry = runtime.provider_registry.require(provider_id)
    target_entry = runtime.target_registry.require(target_id)

    assert provider_entry.enabled is False
    assert provider_entry.provider is None
    assert target_entry.enabled is False
    with pytest.raises(ProviderRegistryError, match="disabled"):
        runtime.provider_registry.resolve_enabled(provider_id)


@pytest.mark.parametrize(
    ("provider_type", "adapter_type"),
    [
        ("pikvm", PiKVMObserveProvider),
        ("redfish", RedfishObserveProvider),
    ],
)
def test_fixture_mode_config_can_build_explicit_fake_provider(
    provider_type: str,
    adapter_type: type,
    tmp_path,
) -> None:
    path = tmp_path / f"{provider_type}-fixture.yaml"
    path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": f"{provider_type}-fixture",
                        "type": provider_type,
                        "enabled": True,
                        "metadata": {"fixture_mode": True},
                    }
                ],
                "targets": [
                    {
                        "id": f"{provider_type}-target",
                        "provider": f"{provider_type}-fixture",
                        "enabled": True,
                        "allowed_modes": ["Observe"],
                    }
                ],
                "default_policy": {"mode": "Observe"},
            }
        ),
        encoding="utf-8",
    )

    runtime = build_runtime(load_config(path))
    provider = runtime.provider_registry.resolve_enabled(f"{provider_type}-fixture")
    target = runtime.target_registry.resolve_enabled(f"{provider_type}-target")

    assert isinstance(provider, adapter_type)
    assert provider.is_real_hardware is False
    assert provider.risk_class == "test_fake_observe_only"
    assert target.provider_id == f"{provider_type}-fixture"


def test_enabled_real_provider_without_fixture_mode_still_rejected(tmp_path) -> None:
    path = tmp_path / "redfish-real.yaml"
    path.write_text(
        json.dumps(
            {
                "providers": [
                    {
                        "id": "redfish-real",
                        "type": "redfish",
                        "enabled": True,
                        "metadata": {"fixture_mode": False},
                    }
                ],
                "targets": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not executable"):
        load_config(path)
