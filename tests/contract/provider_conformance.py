"""Reusable provider conformance checks.

These checks intentionally exercise providers only through already-authorized
provider requests. Interface-level tests remain responsible for proving CLI and
MCP calls route through registries and `ControlPlane`.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any, Callable

from agentickvm.providers.base import Provider, ProviderActionRequest, ProviderActionResult
from agentickvm.providers.transports import FakeTransport

SECRET_VALUE = "must-not-leak-provider-secret"
SECRET_KEYS = ("password", "token", "api_key", "secret", "credential")


def provider_request(capability: str, **params: Any) -> ProviderActionRequest:
    return ProviderActionRequest(
        capability=capability,
        action=capability.partition(".")[2],
        target_id="conformance-target",
        session_id="conformance-session",
        correlation_id=f"conformance-{capability}",
        parameters=params,
    )


def assert_provider_metadata(provider: Provider) -> None:
    status = provider.status()

    assert status.provider_id
    assert status.provider_kind
    assert isinstance(status.enabled, bool)
    assert isinstance(status.is_real_hardware, bool)
    assert status.risk_class
    assert status.supported_capabilities
    assert status.message
    assert SECRET_VALUE not in repr(status)
    assert not any(key in status.__dict__ for key in SECRET_KEYS)


def assert_disabled_provider_fails(disabled_provider: Provider, capability: str) -> None:
    result = disabled_provider.execute_authorized(provider_request(capability))

    assert_structured_result(result)
    assert result.ok is False
    assert result.performed_on_hardware is False
    assert "disabled" in result.message.lower() or "no fake transport" in result.message.lower()


def assert_unsupported_capability_fails(provider: Provider) -> None:
    result = provider.execute_authorized(provider_request("provider.raw_reset"))

    assert_structured_result(result)
    assert result.ok is False
    assert result.performed_on_hardware is False
    assert "unsupported" in result.message.lower()


def assert_unknown_capability_fails(provider: Provider) -> None:
    result = provider.execute_authorized(provider_request("unknown.capability"))

    assert_structured_result(result)
    assert result.ok is False
    assert result.performed_on_hardware is False


def assert_observe_result(provider: Provider, capability: str) -> ProviderActionResult:
    result = provider.execute_authorized(
        provider_request(capability, password=SECRET_VALUE, detail="summary")
    )

    assert_structured_result(result)
    assert result.ok is True
    assert result.performed_on_hardware is False
    assert SECRET_VALUE not in repr(result)
    return result


def assert_observe_only_provider_rejects_mutation(provider: Provider) -> None:
    assert all(capability.startswith("observe.") for capability in provider.supported_capabilities)
    result = provider.execute_authorized(provider_request("power.force_restart"))

    assert_structured_result(result)
    assert result.ok is False
    assert result.performed_on_hardware is False


def assert_fake_transport_used(provider: Provider) -> None:
    client = getattr(provider, "client", None)
    assert client is not None
    assert isinstance(getattr(client, "transport", None), FakeTransport)


def assert_fake_provider_does_not_read_env(
    monkeypatch,
    provider_factory: Callable[[], Provider],
    capability: str,
) -> None:
    monkeypatch.setenv("AGENTICKVM_PASSWORD", SECRET_VALUE)
    monkeypatch.setenv("AGENTICKVM_TOKEN", SECRET_VALUE)

    provider = provider_factory()
    result = provider.execute_authorized(provider_request(capability))

    assert_structured_result(result)
    assert SECRET_VALUE not in repr(result)


def assert_provider_module_has_no_live_io(module: Any) -> None:
    source = inspect.getsource(module)
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


def assert_structured_result(result: ProviderActionResult) -> None:
    assert isinstance(result.ok, bool)
    assert result.provider_id
    assert result.capability
    assert result.action
    assert result.target_id
    assert isinstance(result.performed_on_hardware, bool)
    assert isinstance(result.message, str)
    assert isinstance(result.data, Mapping)
