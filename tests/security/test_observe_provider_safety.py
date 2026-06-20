import inspect

import pytest

from agentickvm.providers import pikvm as pikvm_module
from agentickvm.providers import redfish as redfish_module
from agentickvm.providers.pikvm import PiKVMObserveClient
from agentickvm.providers.redfish import RedfishObserveClient
from agentickvm.providers.transports import FakeTransport, TransportMethodNotAllowedError


def test_observe_provider_modules_have_no_live_io_imports() -> None:
    source = "\n".join(
        [
            inspect.getsource(pikvm_module),
            inspect.getsource(redfish_module),
        ]
    )

    forbidden_imports = (
        "import requests",
        "from requests",
        "import urllib",
        "from urllib",
        "import http.client",
        "from http.client",
        "import socket",
        "from socket",
    )
    for item in forbidden_imports:
        assert item not in source


def test_redfish_fake_transport_rejects_mutating_methods() -> None:
    transport = FakeTransport({("GET", "/redfish/v1/"): {"ok": True}})

    for method in ("POST", "PATCH", "DELETE", "PUT"):
        with pytest.raises(TransportMethodNotAllowedError):
            transport.request(method, "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset")


def test_pikvm_client_exposes_fixture_observe_and_actuation_methods() -> None:
    public = {
        name
        for name in dir(PiKVMObserveClient)
        if not name.startswith("_") and callable(getattr(PiKVMObserveClient, name))
    }

    assert public == {
        "boot_status",
        "event_logs",
        "hardware_inventory",
        "power_state",
        "screen",
        "screenshot_metadata",
        "status",
        "mount_msd",
        "mouse_click",
        "mouse_move",
        "power_cycle",
        "power_off",
        "power_on",
        "reset",
        "type_text",
    }


def test_redfish_client_exposes_observe_only_methods() -> None:
    public = {
        name
        for name in dir(RedfishObserveClient)
        if not name.startswith("_") and callable(getattr(RedfishObserveClient, name))
    }

    assert public == {
        "boot_status",
        "computer_system",
        "event_logs",
        "hardware_inventory",
        "manager_status",
        "power_state",
        "sensors",
        "service_root",
        "systems_collection",
    }
