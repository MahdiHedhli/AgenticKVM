from agentickvm.providers import MockProvider, ProviderActionRequest


def test_mock_provider_never_touches_real_hardware() -> None:
    provider = MockProvider()
    request = ProviderActionRequest(
        capability="observe.status",
        action="status",
        target_id="mock-target",
        session_id="test-session",
        correlation_id="corr-1",
        parameters={"password": "should-not-appear", "detail": "summary"},
    )

    result = provider.execute_authorized(request)

    assert result.ok is True
    assert result.provider_id == "mock"
    assert result.performed_on_hardware is False
    assert result.data["mock"] is True
    assert result.data["performed"] is False
    assert result.data["parameters"]["password"] == "[REDACTED]"
    assert provider.requests == [request]


def test_mock_provider_fails_unsupported_capabilities_without_hardware() -> None:
    provider = MockProvider()
    request = ProviderActionRequest(
        capability="firmware.unknown_flash",
        action="unknown_flash",
        target_id="mock-target",
        session_id="test-session",
        correlation_id="corr-2",
    )

    result = provider.execute_authorized(request)

    assert result.ok is False
    assert result.performed_on_hardware is False
    assert "no hardware action performed" in result.message
