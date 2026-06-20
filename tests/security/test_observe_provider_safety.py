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


def test_pikvm_client_exposes_observe_and_clearance_gated_actuation_methods() -> None:
    public = {
        name
        for name in dir(PiKVMObserveClient)
        if not name.startswith("_") and callable(getattr(PiKVMObserveClient, name))
    }

    observe_methods = {
        "boot_status",
        "event_logs",
        "hardware_inventory",
        "power_state",
        "screen",
        "screenshot_metadata",
        "status",
    }
    # Actuation methods exist on the fixture client but are exercised only after
    # ControlPlane clearance and never reach real hardware (the fixture transport
    # is fake). See tests/security/test_pikvm_actuation_clearance.py.
    actuation_methods = {
        "power_on",
        "power_off",
        "power_cycle",
        "reset",
        "type_text",
        "mouse_move",
        "mouse_click",
        "mount_msd",
    }

    assert public == observe_methods | actuation_methods


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
