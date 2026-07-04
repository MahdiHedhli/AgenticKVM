"""Fixture tests for the pinned, clearance-gated live HTTPS mutation client.

Every test injects a fake connection factory; no socket is created, no real
credential is read, and no mutating request can leave this process. The
default (socket-backed) connection factory is booby-trapped where relevant.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest

from agentickvm.control_plane.act_client import (
    ACTClearanceVerifier,
    MockACTProofVerifier,
    cleared_response_for,
)
from agentickvm.control_plane.clearance import build_clearance_request
from agentickvm.live_validation import http_mutate as http_mutate_module
from agentickvm.live_validation.http_mutate import PinnedMutatingHTTPSJSONClient
from agentickvm.live_validation.pikvm_mutate import (
    build_live_pikvm_mutation_transport,
    pikvm_mutating_http_client_factory,
)
from agentickvm.live_validation.redfish_mutate import (
    build_live_redfish_mutation_transport,
    redfish_mutating_http_client_factory,
)
from agentickvm.providers.errors import (
    ProviderAuthenticationFailedError,
    ProviderMutationBlockedError,
    ProviderProtocolError,
    ProviderTLSVerificationError,
)
from agentickvm.providers.mutation_gate import issue_verified_mutation_clearance
from agentickvm.providers.pikvm_transport import sha256_fingerprint_for_der

NOW = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
FAKE_CERT_DER = b"fake-der-certificate-bytes"
FAKE_CERT_FINGERPRINT = sha256_fingerprint_for_der(FAKE_CERT_DER)
SECRET_PASSWORD = "must-not-leak-live-secret"
TARGET_ID = "lab-node-fixture"
REDFISH_PROVIDER_ID = "redfish-live-fixture"
PIKVM_PROVIDER_ID = "pikvm-live-fixture"
SYSTEM_PATH = "/redfish/v1/Systems/1"


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


class FakeMutationConnection:
    def __init__(
        self,
        *,
        cert_der: bytes | None = FAKE_CERT_DER,
        status: int = 200,
        content_type: str = "application/json",
        raw_body: bytes | None = None,
    ) -> None:
        self.sock = None
        self._cert_der = cert_der
        self._status = status
        self._content_type = content_type
        self._raw_body = raw_body
        self.requests = []
        self.closed = False

    def connect(self) -> None:
        self.sock = FakeSock(self._cert_der)

    def request(self, method, path, body=None, headers=None) -> None:
        self.requests.append(
            {
                "method": method,
                "path": path,
                "body": body,
                "headers": dict(headers or {}),
            }
        )

    def getresponse(self) -> FakeResponse:
        body = self._raw_body if self._raw_body is not None else b'{"TaskState": "Completed"}'
        return FakeResponse(
            status=self._status, body=body, content_type=self._content_type
        )

    def close(self) -> None:
        self.closed = True


class FakeConnectionFactory:
    def __init__(self, connection: FakeMutationConnection) -> None:
        self.connection = connection
        self.calls = []

    def __call__(self, host, port, context, timeout_seconds):
        self.calls.append({"host": host, "port": port})
        return self.connection


def _handle(
    *,
    capability: str = "power.on",
    parameters=None,
    target: str = TARGET_ID,
    provider: str = REDFISH_PROVIDER_ID,
    now: datetime = NOW,
):
    request = build_clearance_request(
        session_id="session-1",
        target=target,
        provider=provider,
        capability=capability,
        parameters={} if parameters is None else parameters,
        risk_family="high_risk",
        risk_summary="mutating hardware action",
        material_risks=("hardware state change",),
        intended_effect="exercise the live mutation client in fixtures",
        requested_by="agent",
        audit_correlation_id="corr-live-mutate",
        policy_context={},
        now=now,
    )
    return issue_verified_mutation_clearance(
        request=request,
        response=cleared_response_for(request),
        verifier=ACTClearanceVerifier(
            tower_id="mock-act",
            proof_verifier=MockACTProofVerifier(),
            test_mode=True,
        ),
        now=now,
    )


def _client(connection: FakeMutationConnection, **overrides) -> PinnedMutatingHTTPSJSONClient:
    params = {
        "host": "redfish.example.invalid",
        "port": 443,
        "headers": {"Authorization": "Basic ZmFrZQ=="},
        "pinned_sha256": FAKE_CERT_FINGERPRINT,
        "clearance": _handle(),
        "connection_factory": FakeConnectionFactory(connection),
        "now_factory": lambda: NOW,
    }
    params.update(overrides)
    return PinnedMutatingHTTPSJSONClient(**params)


def test_mutating_client_requires_a_pinned_fingerprint() -> None:
    with pytest.raises(ProviderMutationBlockedError, match="pin"):
        _client(FakeMutationConnection(), pinned_sha256=None)


def test_mutating_client_requires_a_genuine_clearance_handle() -> None:
    class SpoofedHandle:
        capability = "power.on"
        expires_at = NOW + timedelta(seconds=60)

    for clearance in (None, SpoofedHandle(), "cleared"):
        with pytest.raises(ProviderMutationBlockedError):
            _client(FakeMutationConnection(), clearance=clearance)


def test_mutating_client_refuses_every_non_mutating_method() -> None:
    connection = FakeMutationConnection()
    factory = FakeConnectionFactory(connection)
    client = _client(connection, connection_factory=factory)

    for method in ("GET", "HEAD", "PUT", "DELETE", "OPTIONS", "TRACE"):
        with pytest.raises(ProviderMutationBlockedError):
            client.request_json(method, "/redfish/v1/", {}, timeout_seconds=1.0)

    assert factory.calls == []
    assert connection.requests == []


def test_mutating_client_happy_post_uses_injected_connection(monkeypatch) -> None:
    def _bomb(*args, **kwargs):
        raise AssertionError("real HTTPSConnection must not be constructed in tests")

    monkeypatch.setattr(http_mutate_module, "HTTPSConnection", _bomb)
    connection = FakeMutationConnection()
    client = _client(connection)

    payload = client.post_json(
        f"{SYSTEM_PATH}/Actions/ComputerSystem.Reset",
        {"ResetType": "On"},
        timeout_seconds=1.0,
    )

    assert payload["TaskState"] == "Completed"
    sent = connection.requests[0]
    assert sent["method"] == "POST"
    assert json.loads(sent["body"]) == {"ResetType": "On"}
    assert sent["headers"]["Content-Type"] == "application/json"
    assert connection.closed is True


def test_mutating_client_accepts_empty_success_bodies() -> None:
    connection = FakeMutationConnection(status=204, raw_body=b"", content_type="")
    client = _client(connection)

    payload = client.post_json(
        f"{SYSTEM_PATH}/Actions/ComputerSystem.Reset",
        {"ResetType": "On"},
        timeout_seconds=1.0,
    )

    assert payload == {}


def test_mutating_client_pin_mismatch_blocks_request_and_credentials() -> None:
    connection = FakeMutationConnection(cert_der=b"other-cert")
    client = _client(connection)

    with pytest.raises(ProviderTLSVerificationError, match="credentials were not sent"):
        client.post_json("/redfish/v1/", {}, timeout_seconds=1.0)

    assert connection.requests == []
    assert connection.closed is True


def test_mutating_client_missing_peer_certificate_fails_closed() -> None:
    connection = FakeMutationConnection(cert_der=None)
    client = _client(connection)

    with pytest.raises(ProviderTLSVerificationError):
        client.post_json("/redfish/v1/", {}, timeout_seconds=1.0)

    assert connection.requests == []


def test_mutating_client_refuses_expired_clearance_before_connecting() -> None:
    connection = FakeMutationConnection()
    factory = FakeConnectionFactory(connection)
    client = _client(
        connection,
        connection_factory=factory,
        now_factory=lambda: NOW + timedelta(seconds=3600),
    )

    with pytest.raises(ProviderMutationBlockedError, match="expired"):
        client.post_json("/redfish/v1/", {}, timeout_seconds=1.0)

    assert factory.calls == []


def test_mutating_client_maps_auth_status_and_redacts_public_message() -> None:
    connection = FakeMutationConnection(status=401)
    client = _client(connection)

    with pytest.raises(ProviderAuthenticationFailedError) as excinfo:
        client.post_json("/redfish/v1/", {}, timeout_seconds=1.0)

    assert excinfo.value.public_message == "provider authentication failed"
    assert "ZmFrZQ==" not in repr(excinfo.value)


def test_mutating_client_rejects_error_statuses() -> None:
    connection = FakeMutationConnection(status=500)
    client = _client(connection)

    with pytest.raises(ProviderProtocolError):
        client.post_json("/redfish/v1/", {}, timeout_seconds=1.0)


def test_mutating_client_repr_redacts_host_and_headers() -> None:
    client = _client(FakeMutationConnection())

    text = repr(client)

    assert "redfish.example.invalid" not in text
    assert "ZmFrZQ==" not in text
    assert "[REDACTED]" in text


def test_redfish_mutating_factory_refuses_to_resolve_credentials_without_handle() -> None:
    env = {"REDFISH_LAB_USERNAME": "operator", "REDFISH_LAB_PASSWORD": SECRET_PASSWORD}
    factory = redfish_mutating_http_client_factory(
        env=env,
        connection_factory=FakeConnectionFactory(FakeMutationConnection()),
    )
    transport = build_live_redfish_mutation_transport(
        base_url="https://redfish.example.invalid",
        credential_ref="env://REDFISH_LAB",
        cert_fingerprint=FAKE_CERT_FINGERPRINT,
        target_id=TARGET_ID,
        provider_id=REDFISH_PROVIDER_ID,
        system_path=SYSTEM_PATH,
        tls_probe=_StaticProbe(FAKE_CERT_FINGERPRINT),
        http_client_factory=factory,
        now_factory=lambda: NOW,
    )

    with pytest.raises(ProviderMutationBlockedError):
        transport.power_on(clearance=None)


def test_redfish_mutating_transport_end_to_end_fixture_actuation() -> None:
    connection = FakeMutationConnection()
    env = {"REDFISH_LAB_USERNAME": "operator", "REDFISH_LAB_PASSWORD": SECRET_PASSWORD}
    transport = build_live_redfish_mutation_transport(
        base_url="https://redfish.example.invalid",
        credential_ref="env://REDFISH_LAB",
        cert_fingerprint=FAKE_CERT_FINGERPRINT,
        target_id=TARGET_ID,
        provider_id=REDFISH_PROVIDER_ID,
        system_path=SYSTEM_PATH,
        tls_probe=_StaticProbe(FAKE_CERT_FINGERPRINT),
        http_client_factory=redfish_mutating_http_client_factory(
            env=env, connection_factory=FakeConnectionFactory(connection)
        ),
        now_factory=lambda: NOW,
    )

    result = transport.power_on(clearance=_handle(capability="power.on"))

    assert result["performed"] is True
    sent = connection.requests[0]
    assert sent["method"] == "POST"
    assert sent["path"] == f"{SYSTEM_PATH}/Actions/ComputerSystem.Reset"
    assert json.loads(sent["body"]) == {"ResetType": "On"}
    assert sent["headers"]["Authorization"].startswith("Basic ")
    assert SECRET_PASSWORD not in repr(result)
    assert SECRET_PASSWORD not in repr(transport.__dict__)


def test_build_live_redfish_mutation_transport_requires_pin() -> None:
    with pytest.raises(ProviderMutationBlockedError):
        build_live_redfish_mutation_transport(
            base_url="https://redfish.example.invalid",
            credential_ref="env://REDFISH_LAB",
            cert_fingerprint=None,
            target_id=TARGET_ID,
            provider_id=REDFISH_PROVIDER_ID,
            system_path=SYSTEM_PATH,
            tls_probe=_StaticProbe(FAKE_CERT_FINGERPRINT),
        )


def test_pikvm_mutating_transport_end_to_end_fixture_actuation() -> None:
    connection = FakeMutationConnection(raw_body=b'{"ok": true}')
    env = {"PIKVM_LAB_USERNAME": "operator", "PIKVM_LAB_PASSWORD": SECRET_PASSWORD}
    transport = build_live_pikvm_mutation_transport(
        base_url="https://pikvm.example.invalid",
        credential_ref="env://PIKVM_LAB",
        cert_fingerprint=FAKE_CERT_FINGERPRINT,
        target_id=TARGET_ID,
        provider_id=PIKVM_PROVIDER_ID,
        tls_probe=_StaticProbe(FAKE_CERT_FINGERPRINT),
        http_client_factory=pikvm_mutating_http_client_factory(
            env=env, connection_factory=FakeConnectionFactory(connection)
        ),
        now_factory=lambda: NOW,
    )

    result = transport.power_cycle(
        clearance=_handle(capability="power.power_cycle", provider=PIKVM_PROVIDER_ID)
    )

    assert result["performed"] is True
    sent = connection.requests[0]
    assert sent["method"] == "POST"
    assert sent["path"] == "/api/atx/power/cycle"
    assert sent["headers"]["X-KVMD-User"] == "operator"
    assert SECRET_PASSWORD not in repr(result)
    assert SECRET_PASSWORD not in repr(transport.__dict__)


def test_build_live_pikvm_mutation_transport_requires_pin() -> None:
    with pytest.raises(ProviderMutationBlockedError):
        build_live_pikvm_mutation_transport(
            base_url="https://pikvm.example.invalid",
            credential_ref="env://PIKVM_LAB",
            cert_fingerprint=None,
            target_id=TARGET_ID,
            provider_id=PIKVM_PROVIDER_ID,
            tls_probe=_StaticProbe(FAKE_CERT_FINGERPRINT),
        )


class _StaticProbe:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint

    def certificate_der_sha256(self, *, host: str, port: int, timeout_seconds: float) -> str:
        return self.fingerprint
