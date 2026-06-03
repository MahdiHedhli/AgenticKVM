from agentickvm.providers import redfish as redfish_module
from agentickvm.providers.redfish import (
    RedfishObserveClient,
    RedfishObserveProvider,
    default_redfish_fake_transport,
)

from tests.contract.provider_conformance import (
    assert_disabled_provider_fails,
    assert_fake_provider_does_not_read_env,
    assert_fake_transport_used,
    assert_observe_only_provider_rejects_mutation,
    assert_observe_result,
    assert_provider_metadata,
    assert_provider_module_has_no_live_io,
    assert_unknown_capability_fails,
    assert_unsupported_capability_fails,
)


def _redfish_provider() -> RedfishObserveProvider:
    return RedfishObserveProvider(
        enabled=True,
        client=RedfishObserveClient(transport=default_redfish_fake_transport()),
    )


def test_redfish_provider_conforms_to_provider_metadata_contract() -> None:
    assert_provider_metadata(_redfish_provider())
    assert_provider_metadata(RedfishObserveProvider())


def test_redfish_provider_disabled_and_unsupported_fail_closed() -> None:
    assert_disabled_provider_fails(RedfishObserveProvider(), "observe.power_state")
    assert_unsupported_capability_fails(_redfish_provider())
    assert_unknown_capability_fails(_redfish_provider())


def test_redfish_provider_observe_results_are_structured_and_redacted() -> None:
    for capability in (
        "observe.power_state",
        "observe.hardware_inventory",
        "observe.sensors",
        "observe.event_logs",
        "observe.boot_status",
    ):
        assert_observe_result(_redfish_provider(), capability)


def test_redfish_provider_is_observe_only_and_uses_fake_transport() -> None:
    provider = _redfish_provider()

    assert_observe_only_provider_rejects_mutation(provider)
    assert provider.requests == []
    assert_fake_transport_used(provider)


def test_redfish_provider_does_not_read_environment_secrets(monkeypatch) -> None:
    assert_fake_provider_does_not_read_env(monkeypatch, _redfish_provider, "observe.status")


def test_redfish_provider_has_no_live_io_imports() -> None:
    assert_provider_module_has_no_live_io(redfish_module)
