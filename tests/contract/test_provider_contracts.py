from agentickvm.providers import (
    MockProvider,
    Provider,
    ProviderActionRequest,
)


def _request(capability: str) -> ProviderActionRequest:
    return ProviderActionRequest(
        capability=capability,
        action=capability.partition(".")[2],
        target_id="mock-host",
        session_id="s1",
        correlation_id="corr-provider-contract",
    )


def test_provider_base_contract_requires_authorized_execute_method() -> None:
    assert "execute_authorized" in Provider.__abstractmethods__


def test_provider_status_is_local_and_safe() -> None:
    provider = MockProvider()

    status = provider.status()

    assert status.provider_id == "mock"
    assert status.provider_kind == "mock"
    assert status.enabled is True
    assert status.is_real_hardware is False
    assert "observe.power_state" in status.supported_capabilities


def test_provider_validate_authorized_dry_run_checks_capabilities() -> None:
    provider = MockProvider()

    ok = provider.validate_authorized(_request("observe.power_state"))
    denied = provider.validate_authorized(_request("provider.raw_reset"))

    assert ok.ok is True
    assert ok.message == "provider request is locally valid"
    assert denied.ok is False
    assert denied.message == "unsupported capability"
