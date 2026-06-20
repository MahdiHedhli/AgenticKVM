from agentickvm.providers import pikvm as pikvm_module
from agentickvm.providers.pikvm import (
    PIKVM_ACTUATION_CAPABILITIES,
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
    assert_structured_result,
    assert_unknown_capability_fails,
    assert_unsupported_capability_fails,
    provider_request,
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


def test_pikvm_provider_actuation_is_fixture_backed_and_uses_fake_transport() -> None:
    provider = _pikvm_provider()

    # The PiKVM fixture provider supports actuation capabilities, but at the
    # provider boundary every actuation runs through the fake transport and is
    # reported as never performed on hardware. ControlPlane clearance gating is
    # covered separately in tests/security/test_pikvm_actuation_clearance.py.
    assert PIKVM_ACTUATION_CAPABILITIES <= provider.supported_capabilities

    for capability in sorted(PIKVM_ACTUATION_CAPABILITIES):
        result = provider.execute_authorized(provider_request(capability))
        assert_structured_result(result)
        assert result.ok is True, capability
        assert result.performed_on_hardware is False, capability
        assert result.data["performed"] is False, capability

    assert len(provider.requests) == len(PIKVM_ACTUATION_CAPABILITIES)
    assert_fake_transport_used(provider)


def test_pikvm_provider_does_not_read_environment_secrets(monkeypatch) -> None:
    assert_fake_provider_does_not_read_env(monkeypatch, _pikvm_provider, "observe.status")


def test_pikvm_provider_has_no_live_io_imports() -> None:
    assert_provider_module_has_no_live_io(pikvm_module)
