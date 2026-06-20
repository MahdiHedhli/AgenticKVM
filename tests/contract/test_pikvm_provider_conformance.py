from agentickvm.providers import pikvm as pikvm_module
from agentickvm.providers.pikvm import (
    PiKVMObserveClient,
    PiKVMObserveProvider,
    default_pikvm_fake_transport,
)

from tests.contract.provider_conformance import (
    assert_disabled_provider_fails,
    assert_fake_provider_does_not_read_env,
    assert_fake_transport_used,
    assert_observe_result,
    assert_provider_metadata,
    assert_provider_module_has_no_live_io,
    assert_unknown_capability_fails,
    assert_unsupported_capability_fails,
)


def _pikvm_provider() -> PiKVMObserveProvider:
    return PiKVMObserveProvider(
        enabled=True,
        client=PiKVMObserveClient(transport=default_pikvm_fake_transport()),
    )


def test_pikvm_provider_conforms_to_provider_metadata_contract() -> None:
    assert_provider_metadata(_pikvm_provider())
    assert_provider_metadata(PiKVMObserveProvider())


def test_pikvm_provider_disabled_and_unsupported_fail_closed() -> None:
    assert_disabled_provider_fails(PiKVMObserveProvider(), "observe.status")
    assert_unsupported_capability_fails(_pikvm_provider())
    assert_unknown_capability_fails(_pikvm_provider())


def test_pikvm_provider_observe_results_are_structured_and_redacted() -> None:
    for capability in (
        "observe.screen",
        "observe.screenshot",
        "observe.power_state",
        "observe.hardware_inventory",
        "observe.event_logs",
        "observe.boot_status",
    ):
        assert_observe_result(_pikvm_provider(), capability)


def test_pikvm_provider_is_fake_clearance_gated_and_uses_fake_transport() -> None:
    provider = _pikvm_provider()

    assert provider.risk_class == "test_fake_clearance_gated"
    assert "power.power_cycle" in provider.supported_capabilities
    assert "input.keyboard_type" in provider.supported_capabilities
    assert "media.mount_approved_iso" in provider.supported_capabilities
    assert provider.requests == []
    assert_fake_transport_used(provider)


def test_pikvm_provider_does_not_read_environment_secrets(monkeypatch) -> None:
    assert_fake_provider_does_not_read_env(monkeypatch, _pikvm_provider, "observe.status")


def test_pikvm_provider_has_no_live_io_imports() -> None:
    assert_provider_module_has_no_live_io(pikvm_module)
