import inspect
import json
from pathlib import Path

import pytest

from agentickvm.providers import pikvm as pikvm_module
from agentickvm.providers import redfish as redfish_module
from agentickvm.providers.pikvm import (
    PIKVM_OBSERVE_CAPABILITIES,
    PiKVMObserveClient,
    default_pikvm_fake_transport,
)
from agentickvm.providers.pikvm_transport import (
    PIKVM_BOOT_STATUS_PATH,
    PIKVM_EVENT_LOGS_PATH,
    PIKVM_HARDWARE_INVENTORY_PATH,
    PIKVM_HEALTH_PATH,
    PIKVM_POWER_STATE_PATH,
    PIKVM_SCREENSHOT_METADATA_PATH,
    PIKVM_SCREEN_STATE_PATH,
)
from agentickvm.providers.redfish import (
    REDFISH_OBSERVE_CAPABILITIES,
    RedfishObserveClient,
    default_redfish_fake_transport,
)
from agentickvm.providers.transports import (
    FakeTransport,
    TransportMethodNotAllowedError,
)

ROOT = Path(__file__).resolve().parents[1]


def _fixture(provider: str, name: str) -> dict:
    path = ROOT / "fixtures" / "providers" / provider / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_fake_transport_rejects_non_get_methods() -> None:
    transport = FakeTransport({("GET", "/redfish/v1/"): {"ok": True}})

    with pytest.raises(TransportMethodNotAllowedError):
        transport.request("POST", "/redfish/v1/Actions/Reset")


def test_pikvm_client_reads_fixture_backed_observations() -> None:
    transport = FakeTransport(
        {
            ("GET", PIKVM_HEALTH_PATH): _fixture("pikvm", "status.json"),
            ("GET", PIKVM_SCREEN_STATE_PATH): _fixture("pikvm", "screen.json"),
            ("GET", PIKVM_SCREENSHOT_METADATA_PATH): {
                "artifact": {"kind": "screenshot", "storage": "metadata-only"},
                "sensitive": True,
                "raw_bytes_included": False,
            },
            ("GET", PIKVM_POWER_STATE_PATH): _fixture("pikvm", "power.json"),
            ("GET", PIKVM_BOOT_STATUS_PATH): _fixture("pikvm", "boot.json"),
            ("GET", PIKVM_HARDWARE_INVENTORY_PATH): {"provider": "pikvm"},
            ("GET", PIKVM_EVENT_LOGS_PATH): {"events": []},
        }
    )
    client = PiKVMObserveClient(transport=transport)

    assert client.status()["health"] == "ok"
    assert client.screen()["sensitive"] is True
    assert client.power_state()["power_state"] == "on"
    assert client.boot_status()["boot_status"] == "firmware_prompt"
    assert [call.method for call in transport.calls] == ["GET", "GET", "GET", "GET"]


def test_redfish_client_reads_fixture_backed_observations() -> None:
    transport = FakeTransport(
        {
            ("GET", "/redfish/v1/"): _fixture("redfish", "service-root.json"),
            ("GET", "/redfish/v1/Systems"): _fixture("redfish", "systems.json"),
            ("GET", "/redfish/v1/Systems/System.Embedded.1"): _fixture(
                "redfish",
                "system.json",
            ),
            ("GET", "/redfish/v1/Chassis/1/Sensors"): _fixture(
                "redfish",
                "sensors.json",
            ),
            ("GET", "/redfish/v1/Managers/1/LogServices/EventLog/Entries"): _fixture(
                "redfish",
                "event-log.json",
            ),
            ("GET", "/redfish/v1/Managers/1"): _fixture("redfish", "manager.json"),
        }
    )
    client = RedfishObserveClient(transport=transport)

    assert client.service_root()["RedfishVersion"] == "1.17.0"
    assert client.systems_collection()["Members@odata.count"] == 1
    assert client.power_state()["power_state"] == "On"
    assert client.hardware_inventory()["memory"]["TotalSystemMemoryGiB"] == 64
    assert client.sensors()["Members"][0]["Name"] == "CPU Temp"
    assert client.event_logs()["Members"][0]["Message"] == "Fixture event log entry"
    assert client.boot_status()["boot_source_override"] == "None"
    assert all(call.method == "GET" for call in transport.calls)


def test_provider_client_modules_do_not_define_live_transport_imports() -> None:
    source = "\n".join(
        [
            inspect.getsource(pikvm_module),
            inspect.getsource(redfish_module),
        ]
    )

    assert "import requests" not in source
    assert "import urllib" not in source
    assert "import http.client" not in source
    assert "import socket" not in source


def test_observe_capability_sets_are_read_only() -> None:
    assert all(capability.startswith("observe.") for capability in PIKVM_OBSERVE_CAPABILITIES)
    assert all(capability.startswith("observe.") for capability in REDFISH_OBSERVE_CAPABILITIES)


def test_default_fake_transports_have_no_credentials() -> None:
    pikvm = default_pikvm_fake_transport()
    redfish = default_redfish_fake_transport()

    assert pikvm.request("GET", "/api/status").json()["health"] == "ok"
    assert redfish.request("GET", "/redfish/v1/").json()["RedfishVersion"] == "1.17.0"
