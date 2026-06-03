import inspect

import pytest

from agentickvm.config import load_config
from agentickvm.providers import (
    OBSERVE_ONLY_REAL_PROVIDER_CAPABILITIES,
    PiKVMProviderPlaceholder,
    ProviderActionRequest,
    RealProviderNotEnabledError,
    RedfishProviderPlaceholder,
)
from agentickvm.providers import placeholders as placeholder_module


def _request(capability: str = "observe.power_state") -> ProviderActionRequest:
    return ProviderActionRequest(
        capability=capability,
        action=capability.partition(".")[2],
        target_id="real-placeholder-target",
        session_id="s1",
        correlation_id="corr-placeholder",
    )


def test_placeholder_real_provider_cannot_execute() -> None:
    provider = RedfishProviderPlaceholder()

    with pytest.raises(RealProviderNotEnabledError, match="disabled"):
        provider.execute_authorized(_request())


def test_placeholder_real_provider_does_not_perform_network_calls() -> None:
    source = inspect.getsource(placeholder_module)

    assert "requests" not in source
    assert "http.client" not in source
    assert "urllib" not in source
    assert "socket" not in source


def test_placeholder_real_provider_returns_disabled_status() -> None:
    provider = PiKVMProviderPlaceholder()

    status = provider.status()

    assert status.enabled is False
    assert status.is_real_hardware is True
    assert status.risk_class == "real_hardware_disabled"
    assert "disabled" in status.message


def test_placeholder_real_provider_declares_observe_only_capabilities() -> None:
    provider = RedfishProviderPlaceholder()

    assert provider.supported_capabilities == OBSERVE_ONLY_REAL_PROVIDER_CAPABILITIES
    assert provider.supports("observe.power_state") is True
    assert provider.supports("power.force_restart") is False
    assert provider.validate_authorized(_request()).ok is False


def test_real_provider_placeholder_cannot_be_enabled_by_mock_config(tmp_path) -> None:
    path = tmp_path / "enabled-real.yaml"
    path.write_text(
        """
{
  "providers": [
    {"id": "redfish-lab", "type": "redfish", "enabled": true}
  ],
  "targets": []
}
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="not executable"):
        load_config(path)
