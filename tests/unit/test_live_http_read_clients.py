"""Fixture tests for the shared GET-only live HTTPS read client layer.

Every test injects a fake connection factory; no socket is created and no
credential is read from the real environment. The default (socket-backed)
connection factory is booby-trapped where relevant to prove it is unused.
"""

import json

import pytest

from agentickvm.live_validation import http_read as http_read_module
from agentickvm.live_validation.http_read import (
    GETOnlyHTTPSJSONClient,
    resolve_credential_pair,
)
from agentickvm.live_validation.redfish import (
    build_live_redfish_read_transport,
    collect_redfish_read_evidence,
    redfish_http_client_factory,
)
from agentickvm.providers.errors import (
    ProviderAuthenticationFailedError,
    ProviderAuthenticationRequiredError,
    ProviderConnectionError,
    ProviderMutationBlockedError,
    ProviderProtocolError,
    ProviderResponseValidationError,
    ProviderTLSVerificationError,
)
from agentickvm.providers.pikvm_transport import sha256_fingerprint_for_der

from tests.unit.test_redfish_read_transport import SUPERMICRO_SHAPED_ROUTES

FAKE_CERT_DER = b"fake-der-certificate-bytes"
FAKE_CERT_FINGERPRINT = sha256_fingerprint_for_der(FAKE_CERT_DER)
SECRET_PASSWORD = "must-not-leak-live-secret"


class FakeSock:
    def __init__(self, cert_der: bytes | None) -> None:
        self.cert_der = cert_der

    def getpeercert(self, binary_form: bool = False):
        assert binary_form is True
        return self.cert_der


class FakeResponse:
    def __init__(self, *, status: int, body: bytes, content_type: str) -> None:
        self.status = status
        self._body = body
        self._content_type = content_type

    def read(self, limit: int) -> bytes:
        return self._body[:limit]

    def getheader(self, name: str):
        if name.lower() == "content-type":
            return self._content_type
        return None


class FakeConnection:
    def __init__(
        self,
        *,
        routes,
        cert_der: bytes | None = FAKE_CERT_DER,
        status: int = 200,
        content_type: str = "application/json",
        raw_body: bytes | None = None,
    ) -> None:
        self.routes = routes
        self.sock = None
        self._cert_der = cert_der
        self._status = status
        self._content_type = content_type
        self._raw_body = raw_body
        self.connected = False
        self.closed = False
        self.requests = []
        self._last_path = None

    def connect(self) -> None:
        self.connected = True
        self.sock = FakeSock(self._cert_der)

    def request(self, method: str, path: str, headers=None) -> None:
        self.requests.append({"method": method, "path": path, "headers": dict(headers or {})})
        self._last_path = path

    def getresponse(self) -> FakeResponse:
        if self._raw_body is not None:
            body = self._raw_body
        else:
            payload = self.routes.get(self._last_path, {"missing": True})
            body = json.dumps(payload).encode("utf-8")
        return FakeResponse(
            status=self._status,
            body=body,
            content_type=self._content_type,
        )

    def close(self) -> None:
        self.closed = True


class FakeConnectionFactory:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.calls = []

    def __call__(self, host, port, context, timeout_seconds):
        self.calls.append(
            {"host": host, "port": port, "context": context, "timeout": timeout_seconds}
        )
        return self.connection


def _pinned_client(connection: FakeConnection, **overrides) -> GETOnlyHTTPSJSONClient:
    params = {
        "host": "redfish.example.invalid",
        "port": 443,
        "headers": {"Authorization": "Basic ZmFrZQ=="},
        "pinned_sha256": FAKE_CERT_FINGERPRINT,
        "verify_tls": False,
        "connection_factory": FakeConnectionFactory(connection),
    }
    params.update(overrides)
    return GETOnlyHTTPSJSONClient(**params)


def test_resolve_credential_pair_env_scheme(monkeypatch) -> None:
    env = {"REDFISH_LAB_USERNAME": "operator", "REDFISH_LAB_PASSWORD": SECRET_PASSWORD}

    assert resolve_credential_pair("env://REDFISH_LAB", env=env) == (
        "operator",
        SECRET_PASSWORD,
    )


def test_resolve_credential_pair_file_scheme(tmp_path) -> None:
    path = tmp_path / "redfish-credentials.json"
    path.write_text(
        json.dumps({"username": "operator", "password": SECRET_PASSWORD}),
        encoding="utf-8",
    )

    assert resolve_credential_pair(f"file://{path}") == ("operator", SECRET_PASSWORD)


def test_resolve_credential_pair_failures_never_leak_values(tmp_path) -> None:
    missing_file = tmp_path / "missing.json"
    cases = [
        "env://REDFISH_EMPTY",
        f"file://{missing_file}",
        "keyring://unsupported/scheme",
        "env://",
    ]
    for credential_ref in cases:
        with pytest.raises(ProviderAuthenticationRequiredError) as excinfo:
            resolve_credential_pair(credential_ref, env={})
        text = repr(excinfo.value) + str(excinfo.value)
        assert SECRET_PASSWORD not in text
        assert "REDFISH_EMPTY_PASSWORD=" not in text


def test_get_only_client_refuses_non_get_before_any_connection() -> None:
    connection = FakeConnection(routes=SUPERMICRO_SHAPED_ROUTES)
    factory = FakeConnectionFactory(connection)
    client = _pinned_client(connection, connection_factory=factory)

    for method in ("POST", "PATCH", "PUT", "DELETE"):
        with pytest.raises(ProviderMutationBlockedError):
            client.request_json(method, "/redfish/v1/", timeout_seconds=1.0)

    assert factory.calls == []
    assert connection.requests == []


def test_get_only_client_happy_path_uses_injected_connection(monkeypatch) -> None:
    def _bomb(*args, **kwargs):
        raise AssertionError("real HTTPSConnection must not be constructed in tests")

    monkeypatch.setattr(http_read_module, "HTTPSConnection", _bomb)
    connection = FakeConnection(routes=SUPERMICRO_SHAPED_ROUTES)
    client = _pinned_client(connection)

    payload = client.get_json("/redfish/v1/Systems/1", timeout_seconds=1.0)

    assert payload["PowerState"] == "On"
    assert connection.requests[0]["method"] == "GET"
    assert connection.closed is True


def test_get_only_client_pin_mismatch_blocks_request_and_credentials() -> None:
    connection = FakeConnection(routes=SUPERMICRO_SHAPED_ROUTES, cert_der=b"other-cert")
    client = _pinned_client(connection)

    with pytest.raises(ProviderTLSVerificationError, match="credentials were not sent"):
        client.get_json("/redfish/v1/", timeout_seconds=1.0)

    # The request (with its Authorization header) never crossed the wire.
    assert connection.requests == []
    assert connection.closed is True


def test_get_only_client_missing_peer_certificate_fails_closed() -> None:
    connection = FakeConnection(routes=SUPERMICRO_SHAPED_ROUTES, cert_der=None)
    client = _pinned_client(connection)

    with pytest.raises(ProviderTLSVerificationError):
        client.get_json("/redfish/v1/", timeout_seconds=1.0)

    assert connection.requests == []


def test_get_only_client_refuses_unverified_tls_without_pin() -> None:
    with pytest.raises(ProviderProtocolError):
        GETOnlyHTTPSJSONClient(
            host="redfish.example.invalid",
            port=443,
            headers={},
            pinned_sha256=None,
            verify_tls=False,
        )


def test_get_only_client_maps_auth_status_and_redacts_public_message() -> None:
    connection = FakeConnection(routes=SUPERMICRO_SHAPED_ROUTES, status=401)
    client = _pinned_client(connection)

    with pytest.raises(ProviderAuthenticationFailedError) as excinfo:
        client.get_json("/redfish/v1/", timeout_seconds=1.0)

    assert excinfo.value.public_message == "provider authentication failed"
    assert "Authorization" not in str(excinfo.value)
    assert "ZmFrZQ==" not in repr(excinfo.value)


def test_get_only_client_rejects_non_json_and_oversized_bodies() -> None:
    html = FakeConnection(
        routes={}, raw_body=b"<html>login</html>", content_type="text/html"
    )
    with pytest.raises(ProviderResponseValidationError):
        _pinned_client(html).get_json("/redfish/v1/", timeout_seconds=1.0)

    big_body = b"{" + b" " * (2 * 1024 * 1024) + b"}"
    oversized = FakeConnection(routes={}, raw_body=big_body)
    with pytest.raises(ProviderResponseValidationError, match="exceeded"):
        _pinned_client(oversized).get_json("/redfish/v1/", timeout_seconds=1.0)


def test_get_only_client_wraps_socket_errors_without_target_details() -> None:
    class ExplodingConnection(FakeConnection):
        def connect(self) -> None:
            raise OSError("connect to 10.0.0.99 failed")

    connection = ExplodingConnection(routes={})
    client = _pinned_client(connection)

    with pytest.raises(ProviderConnectionError) as excinfo:
        client.get_json("/redfish/v1/", timeout_seconds=1.0)

    assert "10.0.0.99" not in str(excinfo.value)


def test_get_only_client_repr_redacts_host_and_headers() -> None:
    connection = FakeConnection(routes={})
    client = _pinned_client(connection)

    text = repr(client)

    assert "redfish.example.invalid" not in text
    assert "ZmFrZQ==" not in text
    assert "[REDACTED]" in text


def test_real_redfish_factory_builds_basic_auth_get_only_client() -> None:
    connection = FakeConnection(routes=SUPERMICRO_SHAPED_ROUTES)
    env = {"REDFISH_LAB_USERNAME": "operator", "REDFISH_LAB_PASSWORD": SECRET_PASSWORD}
    factory = redfish_http_client_factory(
        env=env, connection_factory=FakeConnectionFactory(connection)
    )
    transport = build_live_redfish_read_transport(
        base_url="https://redfish.example.invalid",
        credential_ref="env://REDFISH_LAB",
        cert_fingerprint=FAKE_CERT_FINGERPRINT,
        verify_ssl=False,
        tls_probe=_StaticProbe(FAKE_CERT_FINGERPRINT),
        http_client_factory=factory,
    )

    power = transport.power_state()

    assert power["power_state"] == "On"
    header = connection.requests[0]["headers"]["Authorization"]
    assert header.startswith("Basic ")
    assert SECRET_PASSWORD not in repr(power)
    assert SECRET_PASSWORD not in repr(transport.__dict__)


def test_collect_redfish_read_evidence_covers_all_read_ops_and_redacts() -> None:
    connection = FakeConnection(routes=SUPERMICRO_SHAPED_ROUTES)
    env = {"REDFISH_LAB_USERNAME": "operator", "REDFISH_LAB_PASSWORD": SECRET_PASSWORD}
    transport = build_live_redfish_read_transport(
        base_url="https://redfish.example.invalid",
        credential_ref="env://REDFISH_LAB",
        cert_fingerprint=FAKE_CERT_FINGERPRINT,
        verify_ssl=False,
        tls_probe=_StaticProbe(FAKE_CERT_FINGERPRINT),
        http_client_factory=redfish_http_client_factory(
            env=env, connection_factory=FakeConnectionFactory(connection)
        ),
    )

    evidence = collect_redfish_read_evidence(transport)

    assert set(evidence) == {
        "observe.status",
        "observe.power_state",
        "observe.boot_status",
        "observe.hardware_inventory",
        "observe.sensors",
        "observe.event_logs",
    }
    assert all(entry["ok"] for entry in evidence.values())
    serialized = json.dumps(evidence)
    assert SECRET_PASSWORD not in serialized
    assert "Basic " not in serialized


def test_collect_redfish_read_evidence_records_partial_failures() -> None:
    routes = {
        "/redfish/v1/": {
            "RedfishVersion": "1.9.0",
            "Systems": {"@odata.id": "/redfish/v1/Systems"},
        },
        "/redfish/v1/Systems": {"Members": [{"@odata.id": "/redfish/v1/Systems/1"}]},
        "/redfish/v1/Systems/1": SUPERMICRO_SHAPED_ROUTES["/redfish/v1/Systems/1"],
    }
    connection = FakeConnection(routes=routes)
    env = {"REDFISH_LAB_USERNAME": "operator", "REDFISH_LAB_PASSWORD": SECRET_PASSWORD}
    transport = build_live_redfish_read_transport(
        base_url="https://redfish.example.invalid",
        credential_ref="env://REDFISH_LAB",
        cert_fingerprint=FAKE_CERT_FINGERPRINT,
        verify_ssl=False,
        tls_probe=_StaticProbe(FAKE_CERT_FINGERPRINT),
        http_client_factory=redfish_http_client_factory(
            env=env, connection_factory=FakeConnectionFactory(connection)
        ),
    )

    evidence = collect_redfish_read_evidence(transport)

    assert evidence["observe.power_state"]["ok"] is True
    assert evidence["observe.event_logs"]["ok"] is False
    assert "error" in evidence["observe.event_logs"]
    assert SECRET_PASSWORD not in json.dumps(evidence)


class _StaticProbe:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint

    def certificate_der_sha256(self, *, host: str, port: int, timeout_seconds: float) -> str:
        return self.fingerprint
