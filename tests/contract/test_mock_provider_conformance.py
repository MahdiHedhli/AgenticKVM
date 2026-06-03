import inspect

import agentickvm.cli.main as cli_module
import agentickvm.mcp.router as router_module
from agentickvm.providers import MockProvider
from agentickvm.providers import mock as mock_module

from tests.contract.provider_conformance import (
    assert_disabled_provider_fails,
    assert_fake_provider_does_not_read_env,
    assert_observe_result,
    assert_provider_metadata,
    assert_provider_module_has_no_live_io,
    assert_unknown_capability_fails,
    assert_unsupported_capability_fails,
)


def _mock_provider() -> MockProvider:
    return MockProvider()


def test_mock_provider_conforms_to_provider_metadata_contract() -> None:
    assert_provider_metadata(MockProvider())


def test_mock_provider_disabled_and_unsupported_fail_closed() -> None:
    disabled = MockProvider()
    disabled.enabled = False

    assert_disabled_provider_fails(disabled, "observe.status")
    assert disabled.requests == []
    assert_unsupported_capability_fails(MockProvider())
    assert_unknown_capability_fails(MockProvider())


def test_mock_provider_observe_results_are_structured_and_redacted() -> None:
    for capability in (
        "observe.screen",
        "observe.power_state",
        "observe.hardware_inventory",
        "observe.sensors",
        "observe.event_logs",
        "observe.boot_status",
    ):
        assert_observe_result(MockProvider(), capability)


def test_mock_provider_does_not_read_environment_secrets(monkeypatch) -> None:
    assert_fake_provider_does_not_read_env(monkeypatch, _mock_provider, "observe.status")


def test_mock_provider_has_no_live_io_imports() -> None:
    assert_provider_module_has_no_live_io(mock_module)


def test_interfaces_do_not_directly_execute_providers() -> None:
    assert "execute_authorized" not in inspect.getsource(cli_module)
    assert "execute_authorized" not in inspect.getsource(router_module)
