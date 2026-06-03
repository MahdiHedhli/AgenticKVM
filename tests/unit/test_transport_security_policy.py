import pytest

from agentickvm.providers import TransportPolicyError, TransportSecurityPolicy
from agentickvm.providers.transports import FakeTransport, TransportMethodNotAllowedError


def test_transport_policy_defaults_verify_tls() -> None:
    policy = TransportSecurityPolicy()

    assert policy.tls_verify is True
    assert policy.allow_insecure_tls is False
    assert policy.allowed_methods == frozenset({"GET"})
    assert policy.redacted_summary()["tls_verify"] is True


def test_insecure_tls_is_never_default_and_requires_explicit_override() -> None:
    with pytest.raises(TransportPolicyError, match="insecure TLS"):
        TransportSecurityPolicy(tls_verify=False)

    policy = TransportSecurityPolicy(tls_verify=False, allow_insecure_tls=True)

    assert policy.tls_verify is False
    assert policy.allow_insecure_tls is True


def test_redfish_fake_transport_rejects_mutating_methods() -> None:
    transport = FakeTransport({("GET", "/redfish/v1/"): {"ok": True}})

    for method in ("POST", "PATCH", "DELETE"):
        with pytest.raises(TransportMethodNotAllowedError):
            transport.request(method, "/redfish/v1/Systems/1/Actions/Reset")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"connect_timeout_seconds": 0},
        {"read_timeout_seconds": 0},
        {"total_timeout_seconds": 0},
        {"connect_timeout_seconds": 5, "total_timeout_seconds": 1},
        {"max_response_bytes": 0},
        {"max_retries": -1},
    ],
)
def test_timeout_and_size_values_validate(kwargs) -> None:
    with pytest.raises(TransportPolicyError):
        TransportSecurityPolicy(**kwargs)


def test_retry_policy_never_retries_unsafe_operations() -> None:
    policy = TransportSecurityPolicy(max_retries=2)

    assert policy.should_retry(error_code="provider_timeout", capability="observe.sensors")
    assert not policy.should_retry(error_code="provider_timeout", capability="power.force_restart")
    assert not policy.should_retry(error_code="provider_tls_verification", capability="observe.sensors")


def test_policy_output_is_redacted_and_contains_no_targets_or_secrets() -> None:
    summary = TransportSecurityPolicy(max_retries=1).redacted_summary()

    assert "password" not in repr(summary).lower()
    assert "token" not in repr(summary).lower()
    assert "credential" not in repr(summary).lower()
    assert "target" not in summary
    assert "endpoint" not in summary
