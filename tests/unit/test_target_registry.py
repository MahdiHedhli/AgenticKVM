import pytest

from agentickvm.control_plane import (
    ControlMode,
    TargetDefinition,
    TargetRegistry,
    TargetRegistryError,
)
from agentickvm.providers import MockProvider, ProviderEntry, ProviderRegistry


def _provider_registry() -> ProviderRegistry:
    return ProviderRegistry(
        [
            ProviderEntry(
                provider_id="mock",
                provider_type="mock",
                provider=MockProvider(),
            )
        ]
    )


def test_target_registration_requires_known_provider() -> None:
    provider_registry = _provider_registry()
    target = TargetDefinition(
        target_id="mock-host",
        provider_id="mock",
        name="Mock Host",
        environment="test",
        labels=("mock", "safe"),
        risk_tier="low",
        allowed_modes=frozenset({ControlMode.OBSERVE, ControlMode.SUPERVISED}),
        metadata={"notes": "safe metadata only"},
    )
    registry = TargetRegistry(provider_registry=provider_registry, targets=[target])

    resolved = registry.resolve_enabled("mock-host", mode=ControlMode.OBSERVE)

    assert resolved.provider_id == "mock"
    assert resolved.metadata["notes"] == "safe metadata only"
    assert registry.list()[0].target_id == "mock-host"


def test_unknown_target_denied() -> None:
    registry = TargetRegistry(provider_registry=_provider_registry())

    with pytest.raises(TargetRegistryError, match="Unknown target id"):
        registry.require("missing")

    with pytest.raises(TargetRegistryError, match="Unknown target id"):
        registry.resolve_enabled("missing")


def test_duplicate_target_rejected() -> None:
    target = TargetDefinition(target_id="mock-host", provider_id="mock")

    with pytest.raises(TargetRegistryError, match="Duplicate target id"):
        TargetRegistry(
            provider_registry=_provider_registry(),
            targets=[target, target],
        )


def test_target_referencing_unknown_provider_rejected() -> None:
    with pytest.raises(TargetRegistryError, match="unknown provider"):
        TargetRegistry(
            provider_registry=_provider_registry(),
            targets=[TargetDefinition(target_id="bad-host", provider_id="missing")],
        )


def test_disabled_target_denied() -> None:
    registry = TargetRegistry(
        provider_registry=_provider_registry(),
        targets=[
            TargetDefinition(
                target_id="mock-host",
                provider_id="mock",
                enabled=False,
            )
        ],
    )

    with pytest.raises(TargetRegistryError, match="disabled"):
        registry.resolve_enabled("mock-host")


def test_target_metadata_rejects_secret_like_keys() -> None:
    with pytest.raises(TargetRegistryError, match="must not contain secrets"):
        TargetDefinition(
            target_id="mock-host",
            provider_id="mock",
            metadata={"nested": {"api_token": "do-not-allow"}},
        )


def test_target_allowed_modes_are_enforced() -> None:
    registry = TargetRegistry(
        provider_registry=_provider_registry(),
        targets=[
            TargetDefinition(
                target_id="mock-host",
                provider_id="mock",
                allowed_modes=frozenset({ControlMode.OBSERVE, ControlMode.SUPERVISED}),
            )
        ],
    )

    assert registry.resolve_enabled("mock-host", mode="Observe").target_id == "mock-host"
    with pytest.raises(TargetRegistryError, match="does not allow mode"):
        registry.resolve_enabled("mock-host", mode=ControlMode.FULL_CONTROL)


def test_provider_target_mismatch_fails_closed() -> None:
    registry = TargetRegistry(
        provider_registry=_provider_registry(),
        targets=[TargetDefinition(target_id="mock-host", provider_id="mock")],
    )

    with pytest.raises(TargetRegistryError, match="configured for provider mock"):
        registry.validate_provider_match("mock-host", "redfish-lab")
