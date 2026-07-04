"""Fixture tests for the socket-free Redfish live MUTATION transport seam.

Every collaborator is an injected fake: the TLS probe, the POST/PATCH client,
and the clearance verifier. No socket opens, no credential resolves, and no
mutating request can leave this process.
"""

from datetime import UTC, datetime, timedelta

import pytest

from agentickvm.control_plane.act_client import (
    ACTClearanceVerifier,
    MockACTProofVerifier,
    cleared_response_for,
)
from agentickvm.control_plane.clearance import build_clearance_request
from agentickvm.providers.errors import (
    ProviderMutationBlockedError,
    ProviderProtocolError,
)
from agentickvm.providers.mutation_gate import issue_verified_mutation_clearance
from agentickvm.providers.redfish_mutation_transport import (
    LiveRedfishMutationTransport,
    REDFISH_BOOT_OVERRIDE_TARGETS,
    REDFISH_LIVE_MUTATING_OPERATIONS,
    RedfishMutationHTTPClientFactory,
)
from agentickvm.providers.redfish_transport import (
    REDFISH_LIVE_READ_OPERATIONS,
    RedfishCredentialRef,
    RedfishFingerprintMismatchError,
    RedfishTargetConfig,
)

NOW = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
GOOD_FINGERPRINT = "aa" * 32
BAD_FINGERPRINT = "bb" * 32
TARGET_ID = "lab-node-fixture"
PROVIDER_ID = "redfish-live-fixture"
SYSTEM_PATH = "/redfish/v1/Systems/1"


class _StaticProbe:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint

    def certificate_der_sha256(self, *, host: str, port: int, timeout_seconds: float) -> str:
        return self.fingerprint


class FakeMutationClient:
    def __init__(self, trust) -> None:
        self.trust = trust
        self.posts = []
        self.patches = []

    def post_json(self, path, body, *, timeout_seconds):
        self.posts.append({"path": path, "body": dict(body)})
        return {"TaskState": "Completed"}

    def patch_json(self, path, body, *, timeout_seconds):
        self.patches.append({"path": path, "body": dict(body)})
        return {"TaskState": "Completed"}


class RecordingMutationClientFactory:
    """Record factory calls; the mutating client is built per actuation only."""

    def __init__(self) -> None:
        self.calls = []
        self.clients: list[FakeMutationClient] = []

    def __call__(self, config, credential_ref, trust, clearance):
        self.calls.append(
            {"trust": trust, "clearance": clearance, "credential_ref": credential_ref}
        )
        client = FakeMutationClient(trust)
        self.clients.append(client)
        return client


def _config(*, fingerprint: str | None = GOOD_FINGERPRINT) -> RedfishTargetConfig:
    return RedfishTargetConfig(
        base_url="https://redfish.example.invalid",
        cert_fingerprint=fingerprint,
        verify_ssl=fingerprint is None,
    )


def _handle(*, capability: str, parameters, now: datetime = NOW):
    request = build_clearance_request(
        session_id="session-1",
        target=TARGET_ID,
        provider=PROVIDER_ID,
        capability=capability,
        parameters=parameters,
        risk_family="high_risk",
        risk_summary="mutating hardware action",
        material_risks=("hardware state change",),
        intended_effect="exercise the redfish mutation seam",
        requested_by="agent",
        audit_correlation_id="corr-redfish-mutation",
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


def _transport(
    *,
    factory: RedfishMutationHTTPClientFactory | None = None,
    fingerprint: str | None = GOOD_FINGERPRINT,
    probe_fingerprint: str = GOOD_FINGERPRINT,
    now_factory=None,
) -> LiveRedfishMutationTransport:
    return LiveRedfishMutationTransport(
        config=_config(fingerprint=fingerprint),
        credential_ref=RedfishCredentialRef("env://REDFISH_LAB"),
        target_id=TARGET_ID,
        provider_id=PROVIDER_ID,
        system_path=SYSTEM_PATH,
        tls_probe=_StaticProbe(probe_fingerprint),
        http_client_factory=factory or RecordingMutationClientFactory(),
        now_factory=now_factory or (lambda: NOW),
    )


def test_mutating_operations_are_a_separate_explicit_set() -> None:
    assert REDFISH_LIVE_MUTATING_OPERATIONS == frozenset(
        {"power.on", "power.force_off", "power.power_cycle", "boot.override"}
    )
    assert not REDFISH_LIVE_MUTATING_OPERATIONS & REDFISH_LIVE_READ_OPERATIONS


def test_transport_refuses_config_without_pinned_fingerprint() -> None:
    factory = RecordingMutationClientFactory()

    with pytest.raises(ProviderMutationBlockedError, match="pin"):
        _transport(factory=factory, fingerprint=None)

    assert factory.calls == []


def test_pin_preflight_mismatch_aborts_before_any_client_exists() -> None:
    factory = RecordingMutationClientFactory()

    with pytest.raises(RedfishFingerprintMismatchError):
        _transport(factory=factory, probe_fingerprint=BAD_FINGERPRINT)

    assert factory.calls == []


@pytest.mark.parametrize(
    ("capability", "method", "reset_type"),
    [
        ("power.on", "power_on", "On"),
        ("power.force_off", "power_force_off", "ForceOff"),
        ("power.power_cycle", "power_cycle", "PowerCycle"),
    ],
)
def test_power_verbs_post_computer_system_reset_with_verified_clearance(
    capability: str, method: str, reset_type: str
) -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)
    handle = _handle(capability=capability, parameters={})

    result = getattr(transport, method)(clearance=handle)

    assert result["performed"] is True
    assert result["capability"] == capability
    client = factory.clients[-1]
    assert client.posts == [
        {
            "path": f"{SYSTEM_PATH}/Actions/ComputerSystem.Reset",
            "body": {"ResetType": reset_type},
        }
    ]
    assert factory.calls[-1]["clearance"] is handle


def test_boot_override_patches_system_resource_once() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)
    handle = _handle(capability="boot.override", parameters={"boot_target": "Pxe"})

    result = transport.set_boot_override(boot_target="Pxe", clearance=handle)

    assert result["performed"] is True
    client = factory.clients[-1]
    assert client.patches == [
        {
            "path": SYSTEM_PATH,
            "body": {
                "Boot": {
                    "BootSourceOverrideTarget": "Pxe",
                    "BootSourceOverrideEnabled": "Once",
                }
            },
        }
    ]


def test_boot_override_refuses_targets_outside_allowlist() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)
    handle = _handle(
        capability="boot.override", parameters={"boot_target": "UefiHttp"}
    )

    assert "UefiHttp" not in REDFISH_BOOT_OVERRIDE_TARGETS
    with pytest.raises(ProviderMutationBlockedError):
        transport.set_boot_override(boot_target="UefiHttp", clearance=handle)

    assert factory.calls == []


def test_mutating_verbs_refuse_without_clearance_handle() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)

    for call in (
        lambda: transport.power_on(clearance=None),
        lambda: transport.power_force_off(clearance=None),
        lambda: transport.power_cycle(clearance=None),
        lambda: transport.set_boot_override(boot_target="Pxe", clearance=None),
    ):
        with pytest.raises(ProviderMutationBlockedError):
            call()

    assert factory.calls == []


def test_mutating_verbs_refuse_capability_mismatched_handle() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)
    handle = _handle(capability="power.on", parameters={})

    with pytest.raises(ProviderMutationBlockedError):
        transport.power_force_off(clearance=handle)

    assert factory.calls == []


def test_boot_override_refuses_params_fingerprint_mismatch() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)
    handle = _handle(capability="boot.override", parameters={"boot_target": "Pxe"})

    with pytest.raises(ProviderMutationBlockedError):
        transport.set_boot_override(boot_target="Hdd", clearance=handle)

    assert factory.calls == []


def test_handles_are_single_use_per_transport() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)
    handle = _handle(capability="power.on", parameters={})

    transport.power_on(clearance=handle)
    with pytest.raises(ProviderMutationBlockedError, match="replay"):
        transport.power_on(clearance=handle)

    assert len(factory.calls) == 1


def test_expired_handle_is_refused_at_call_time() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(
        factory=factory, now_factory=lambda: NOW + timedelta(seconds=3600)
    )
    handle = _handle(capability="power.on", parameters={})

    with pytest.raises(ProviderMutationBlockedError, match="expired"):
        transport.power_on(clearance=handle)

    assert factory.calls == []


def test_target_mismatched_handle_is_refused() -> None:
    factory = RecordingMutationClientFactory()
    transport = LiveRedfishMutationTransport(
        config=_config(),
        credential_ref=RedfishCredentialRef("env://REDFISH_LAB"),
        target_id="different-target",
        provider_id=PROVIDER_ID,
        system_path=SYSTEM_PATH,
        tls_probe=_StaticProbe(GOOD_FINGERPRINT),
        http_client_factory=factory,
        now_factory=lambda: NOW,
    )
    handle = _handle(capability="power.on", parameters={})

    with pytest.raises(ProviderMutationBlockedError):
        transport.power_on(clearance=handle)

    assert factory.calls == []


def test_system_path_must_be_a_redfish_resource_path() -> None:
    for bad_path in ("", "Systems/1", "/api/other", "/redfish/v1/Systems/1/../1"):
        with pytest.raises(ProviderProtocolError):
            LiveRedfishMutationTransport(
                config=_config(),
                credential_ref=RedfishCredentialRef("env://REDFISH_LAB"),
                target_id=TARGET_ID,
                provider_id=PROVIDER_ID,
                system_path=bad_path,
                tls_probe=_StaticProbe(GOOD_FINGERPRINT),
                http_client_factory=RecordingMutationClientFactory(),
            )


def test_actuation_results_and_errors_never_leak_target_details() -> None:
    factory = RecordingMutationClientFactory()
    transport = _transport(factory=factory)
    handle = _handle(capability="power.on", parameters={})

    result = transport.power_on(clearance=handle)

    assert "redfish.example.invalid" not in repr(result)
    with pytest.raises(ProviderMutationBlockedError) as excinfo:
        transport.power_on(clearance=handle)
    assert "redfish.example.invalid" not in str(excinfo.value)
