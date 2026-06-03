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
    assert result.data["simulated"] is True
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


def test_mock_provider_tracks_fake_power_state() -> None:
    provider = MockProvider()

    on = provider.execute_authorized(
        ProviderActionRequest(
            capability="power.on",
            action="on",
            target_id="mock-target",
            session_id="test-session",
            correlation_id="corr-power-on",
        )
    )
    off = provider.execute_authorized(
        ProviderActionRequest(
            capability="power.force_off",
            action="force_off",
            target_id="mock-target",
            session_id="test-session",
            correlation_id="corr-power-off",
        )
    )

    assert on.performed_on_hardware is False
    assert on.data["power_state"] == "on"
    assert off.data["power_state"] == "off"
    assert provider.state.power_state == "off"
    assert provider.state.simulated_events[-1]["capability"] == "power.force_off"


def test_mock_provider_tracks_fake_media_and_boot_state() -> None:
    provider = MockProvider()

    media = provider.execute_authorized(
        ProviderActionRequest(
            capability="media.mount_approved_iso",
            action="mount_approved_iso",
            target_id="mock-target",
            session_id="test-session",
            correlation_id="corr-media",
            parameters={"image": "installer.iso"},
        )
    )
    boot = provider.execute_authorized(
        ProviderActionRequest(
            capability="boot.override",
            action="override",
            target_id="mock-target",
            session_id="test-session",
            correlation_id="corr-boot",
            parameters={"device": "cd"},
        )
    )

    assert media.data["mounted_media"] == "installer.iso"
    assert boot.data["boot_override"] == "cd"
    assert provider.state.mounted_media == "installer.iso"
    assert provider.state.boot_override == "cd"


def test_mock_provider_simulates_dangerous_storage_without_hardware() -> None:
    provider = MockProvider()

    result = provider.execute_authorized(
        ProviderActionRequest(
            capability="storage.wipe_disk",
            action="wipe_disk",
            target_id="mock-target",
            session_id="test-session",
            correlation_id="corr-storage",
            parameters={"disk": "mock-disk-0"},
        )
    )

    assert result.ok is True
    assert result.performed_on_hardware is False
    assert result.data["destructive_effect_simulated"] is True
    assert result.data["storage_layout"]["disks"][0]["id"] == "mock-disk-0"
