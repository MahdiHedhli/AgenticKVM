"""Fail-closed issuance and consumption of verified mutation-clearance handles.

The mutating live transports may only actuate when handed a
``VerifiedMutationClearance`` issued from a cleared, Ed25519-proof-verified ACT
response. Every gap (no proof, bad proof, fingerprint mismatch, expiry, replay,
forged handle) must refuse fail-closed. No test here touches the network.
"""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from agentickvm.control_plane.act_client import (
    ACTClearanceVerifier,
    MockACTProofVerifier,
    cleared_response_for,
)
from agentickvm.control_plane.clearance import ClearanceStatus, build_clearance_request
from agentickvm.control_plane.fingerprints import fingerprint_parameters
from agentickvm.providers.errors import ProviderMutationBlockedError
from agentickvm.providers.mutation_gate import (
    MutationClearanceLedger,
    VerifiedMutationClearance,
    issue_verified_mutation_clearance,
    require_verified_mutation_clearance,
)

NOW = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)
TARGET = "lab-node-fixture"
PROVIDER = "redfish-live-fixture"
BOOT_PARAMS = {"boot_target": "Pxe"}


def _clearance_request(*, capability: str = "boot.override", parameters=None):
    return build_clearance_request(
        session_id="session-1",
        target=TARGET,
        provider=PROVIDER,
        capability=capability,
        parameters=BOOT_PARAMS if parameters is None else parameters,
        risk_family="high_risk",
        risk_summary="mutating hardware action",
        material_risks=("hardware state change",),
        intended_effect="exercise the mutation gate in fixtures",
        requested_by="agent",
        audit_correlation_id="corr-mutation-gate",
        policy_context={},
        now=NOW,
    )


def _verifier() -> ACTClearanceVerifier:
    return ACTClearanceVerifier(
        tower_id="mock-act",
        proof_verifier=MockACTProofVerifier(),
        test_mode=True,
    )


def _issued_handle(*, capability: str = "boot.override", parameters=None):
    request = _clearance_request(capability=capability, parameters=parameters)
    response = cleared_response_for(request)
    return issue_verified_mutation_clearance(
        request=request,
        response=response,
        verifier=_verifier(),
        now=NOW,
    )


def test_issue_returns_handle_for_cleared_verified_response() -> None:
    request = _clearance_request()
    response = cleared_response_for(request)

    handle = issue_verified_mutation_clearance(
        request=request,
        response=response,
        verifier=_verifier(),
        now=NOW,
    )

    assert isinstance(handle, VerifiedMutationClearance)
    assert handle.capability == "boot.override"
    assert handle.target == TARGET
    assert handle.provider == PROVIDER
    assert handle.params_fingerprint == str(request.params_fingerprint)
    assert handle.expires_at == request.expires_at


def test_issue_refuses_without_verifier() -> None:
    request = _clearance_request()
    response = cleared_response_for(request)

    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=request,
            response=response,
            verifier=None,
            now=NOW,
        )


@pytest.mark.parametrize(
    "status",
    [
        ClearanceStatus.CLEARANCE_REQUIRED,
        ClearanceStatus.DENIED,
        ClearanceStatus.EXPIRED,
        ClearanceStatus.INVALID,
        ClearanceStatus.TOWER_UNAVAILABLE,
    ],
)
def test_issue_refuses_every_non_cleared_status(status: ClearanceStatus) -> None:
    request = _clearance_request()
    response = replace(cleared_response_for(request), status=status)

    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=request,
            response=response,
            verifier=_verifier(),
            now=NOW,
        )


def test_issue_refuses_missing_proof() -> None:
    request = _clearance_request()
    response = replace(cleared_response_for(request), proof=None)

    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=request,
            response=response,
            verifier=_verifier(),
            now=NOW,
        )


def test_issue_refuses_bad_proof() -> None:
    request = _clearance_request()
    response = replace(
        cleared_response_for(request), proof={"mock_act_proof": "forged"}
    )

    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=request,
            response=response,
            verifier=_verifier(),
            now=NOW,
        )


def test_issue_refuses_params_fingerprint_mismatch() -> None:
    request = _clearance_request()
    response = replace(
        cleared_response_for(request),
        params_fingerprint=fingerprint_parameters({"boot_target": "Hdd"}),
    )

    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=request,
            response=response,
            verifier=_verifier(),
            now=NOW,
        )


def test_issue_refuses_expired_clearance() -> None:
    request = _clearance_request()
    response = cleared_response_for(request)

    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=request,
            response=response,
            verifier=_verifier(),
            now=NOW + timedelta(seconds=3600),
        )


def test_issue_refuses_observe_capabilities() -> None:
    request = _clearance_request(capability="observe.status", parameters={})
    response = cleared_response_for(request)

    with pytest.raises(ProviderMutationBlockedError):
        issue_verified_mutation_clearance(
            request=request,
            response=response,
            verifier=_verifier(),
            now=NOW,
        )


def test_handles_cannot_be_forged_by_direct_construction() -> None:
    with pytest.raises(ProviderMutationBlockedError):
        VerifiedMutationClearance(
            request_id="forged",
            capability="power.on",
            target=TARGET,
            provider=PROVIDER,
            params_fingerprint=fingerprint_parameters({}),
            risk_family="high_risk",
            expires_at=NOW + timedelta(seconds=60),
            tower_id="mock-act",
            issued_at=NOW,
        )


def test_require_accepts_matching_single_use_handle() -> None:
    handle = _issued_handle()
    ledger = MutationClearanceLedger()

    require_verified_mutation_clearance(
        handle,
        capability="boot.override",
        parameters=BOOT_PARAMS,
        target=TARGET,
        provider=PROVIDER,
        now=NOW,
        ledger=ledger,
    )


def test_require_refuses_replayed_handle() -> None:
    handle = _issued_handle()
    ledger = MutationClearanceLedger()
    require_verified_mutation_clearance(
        handle,
        capability="boot.override",
        parameters=BOOT_PARAMS,
        target=TARGET,
        provider=PROVIDER,
        now=NOW,
        ledger=ledger,
    )

    with pytest.raises(ProviderMutationBlockedError, match="replay"):
        require_verified_mutation_clearance(
            handle,
            capability="boot.override",
            parameters=BOOT_PARAMS,
            target=TARGET,
            provider=PROVIDER,
            now=NOW,
            ledger=ledger,
        )


def test_require_refuses_missing_and_spoofed_handles() -> None:
    class SpoofedHandle:
        request_id = "spoof"
        capability = "boot.override"
        target = TARGET
        provider = PROVIDER
        params_fingerprint = fingerprint_parameters(BOOT_PARAMS)
        expires_at = NOW + timedelta(seconds=60)

    for clearance in (None, SpoofedHandle(), "cleared", object()):
        with pytest.raises(ProviderMutationBlockedError):
            require_verified_mutation_clearance(
                clearance,
                capability="boot.override",
                parameters=BOOT_PARAMS,
                target=TARGET,
                provider=PROVIDER,
                now=NOW,
                ledger=MutationClearanceLedger(),
            )


def test_require_refuses_capability_mismatch() -> None:
    handle = _issued_handle(capability="power.on", parameters={})

    with pytest.raises(ProviderMutationBlockedError):
        require_verified_mutation_clearance(
            handle,
            capability="power.force_off",
            parameters={},
            target=TARGET,
            provider=PROVIDER,
            now=NOW,
            ledger=MutationClearanceLedger(),
        )


def test_require_refuses_params_fingerprint_mismatch() -> None:
    handle = _issued_handle()

    with pytest.raises(ProviderMutationBlockedError) as excinfo:
        require_verified_mutation_clearance(
            handle,
            capability="boot.override",
            parameters={"boot_target": "Hdd"},
            target=TARGET,
            provider=PROVIDER,
            now=NOW,
            ledger=MutationClearanceLedger(),
        )

    text = repr(excinfo.value) + str(excinfo.value)
    assert "Hdd" not in text
    assert "Pxe" not in text


def test_require_refuses_target_and_provider_mismatch() -> None:
    handle = _issued_handle()

    with pytest.raises(ProviderMutationBlockedError):
        require_verified_mutation_clearance(
            handle,
            capability="boot.override",
            parameters=BOOT_PARAMS,
            target="other-target",
            provider=PROVIDER,
            now=NOW,
            ledger=MutationClearanceLedger(),
        )
    with pytest.raises(ProviderMutationBlockedError):
        require_verified_mutation_clearance(
            handle,
            capability="boot.override",
            parameters=BOOT_PARAMS,
            target=TARGET,
            provider="other-provider",
            now=NOW,
            ledger=MutationClearanceLedger(),
        )


def test_require_refuses_expired_handle_at_call_time() -> None:
    handle = _issued_handle()

    with pytest.raises(ProviderMutationBlockedError, match="expired"):
        require_verified_mutation_clearance(
            handle,
            capability="boot.override",
            parameters=BOOT_PARAMS,
            target=TARGET,
            provider=PROVIDER,
            now=NOW + timedelta(seconds=3600),
            ledger=MutationClearanceLedger(),
        )
