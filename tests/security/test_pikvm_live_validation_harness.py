"""Mock-only coverage for the supervised PiKVM live-validation harness.

The harness in ``agentickvm.live_validation`` supports operator-run validation
against real hardware. CI must never contact a device, so these tests inject a
fake TLS probe and exercise only the pure logic: precondition hygiene,
credential-reference redaction, certificate-pinning preflight (match vs.
mismatch), and the human-checkpoint gate between stages.

No socket is opened and no credential is resolved anywhere in this module.
"""

from __future__ import annotations

import json

import pytest

from agentickvm.live_validation import (
    PiKVMLiveValidationError,
    StageCheckpoint,
    ValidationPreconditions,
    build_stage_checkpoint,
    deliberately_wrong_fingerprint,
    load_preconditions,
    run_stage1_cert_preflight,
    validate_prior_checkpoint,
)
from agentickvm.providers.pikvm_transport import normalize_cert_fingerprint

BASE_URL = "https://pikvm.example:443"
CREDENTIAL_REF = "keychain://agentickvm/example"
FAKE_FINGERPRINT = "ab" * 32  # 64 hex chars -> a valid SHA-256 fingerprint


class _FakeTLSProbe:
    """Returns a fixed fingerprint; never touches the network."""

    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint
        self.calls = 0

    def certificate_der_sha256(self, *, host: str, port: int, timeout_seconds: float) -> str:
        self.calls += 1
        return self.fingerprint


def _preconditions(**overrides: str) -> ValidationPreconditions:
    base = {
        "sacrificial_target": "lab-pikvm-01",
        "isolated_segment": "vlan-validation",
        "credential_ref": CREDENTIAL_REF,
        "firmware_version": "3.291",
        "operator": "operator@example",
        "confirmed_at": "2026-06-13T12:00:00+00:00",
    }
    base.update(overrides)
    return ValidationPreconditions(**base)


def test_preconditions_reject_missing_fields() -> None:
    with pytest.raises(PiKVMLiveValidationError, match="missing live validation precondition"):
        _preconditions(sacrificial_target="")


def test_preconditions_reject_raw_secret_credential_ref() -> None:
    with pytest.raises(PiKVMLiveValidationError, match="reference, not a raw secret"):
        _preconditions(credential_ref="password=hunter2")


def test_preconditions_to_dict_redacts_credential_ref() -> None:
    payload = _preconditions().to_dict()

    assert payload["credential_ref"] == "[CREDENTIAL_REF]"
    assert CREDENTIAL_REF not in json.dumps(payload)
    assert payload["sacrificial_target"] == "lab-pikvm-01"


def test_load_preconditions_reads_operator_json(tmp_path) -> None:
    path = tmp_path / "preconditions.json"
    path.write_text(
        json.dumps(
            {
                "sacrificial_target": "lab-pikvm-01",
                "isolated_segment": "vlan-validation",
                "credential_ref": CREDENTIAL_REF,
                "firmware_version": "3.291",
                "operator": "operator@example",
                "confirmed_at": "2026-06-13T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    preconditions = load_preconditions(path)

    assert preconditions.sacrificial_target == "lab-pikvm-01"
    assert preconditions.to_dict()["credential_ref"] == "[CREDENTIAL_REF]"


def test_stage1_preflight_pins_cert_and_never_auto_confirms() -> None:
    probe = _FakeTLSProbe(FAKE_FINGERPRINT)

    checkpoint = run_stage1_cert_preflight(
        base_url=BASE_URL,
        credential_ref=CREDENTIAL_REF,
        cert_fingerprint=FAKE_FINGERPRINT,
        verify_ssl=True,
        tls_probe=probe,
    )

    assert probe.calls >= 1
    assert checkpoint.stage == "stage1-cert-pinning-preflight"
    assert checkpoint.status == "operator_review_required"
    assert checkpoint.next_stage == "stage2-observe"
    assert checkpoint.operator_confirmed is False

    details = checkpoint.details
    # The observed fingerprint is recorded exactly as the probe returned it.
    assert details["observed_cert_fingerprint"] == FAKE_FINGERPRINT
    assert details["credential_ref"] == "[CREDENTIAL_REF]"
    # A matching pin hands trust to the authenticated client...
    assert details["pinned_match_built_authenticated_client"] is True
    # ...while a wrong pin aborts before any credential is handed over.
    assert details["wrong_fingerprint_aborted_before_credentials"] is True
    assert details["verify_ssl_false_without_pin_rejected"] is True

    # The checkpoint payload must never carry the raw credential reference.
    assert CREDENTIAL_REF not in json.dumps(checkpoint.to_dict())


def test_stage1_preflight_requires_https_base_url() -> None:
    with pytest.raises(Exception):
        run_stage1_cert_preflight(
            base_url="http://pikvm.example",
            credential_ref=CREDENTIAL_REF,
            cert_fingerprint=FAKE_FINGERPRINT,
            verify_ssl=True,
            tls_probe=_FakeTLSProbe(FAKE_FINGERPRINT),
        )


def test_build_stage_checkpoint_never_auto_confirms() -> None:
    checkpoint = build_stage_checkpoint(
        stage="stage2-observe",
        status="operator_review_required",
        next_stage="stage3-input",
        details={"ok": True},
    )

    assert isinstance(checkpoint, StageCheckpoint)
    assert checkpoint.operator_confirmed is False
    assert checkpoint.generated_at  # ISO timestamp present


def test_validate_prior_checkpoint_requires_operator_confirmation(tmp_path) -> None:
    path = tmp_path / "stage1.json"
    unconfirmed = build_stage_checkpoint(
        stage="stage1-cert-pinning-preflight",
        status="operator_review_required",
        next_stage="stage2-observe",
        details={"ok": True},
    ).to_dict()
    path.write_text(json.dumps(unconfirmed), encoding="utf-8")

    with pytest.raises(PiKVMLiveValidationError, match="must confirm"):
        validate_prior_checkpoint(path, expected_stage="stage1-cert-pinning-preflight")


def test_validate_prior_checkpoint_rejects_wrong_stage(tmp_path) -> None:
    path = tmp_path / "stage1.json"
    payload = build_stage_checkpoint(
        stage="stage1-cert-pinning-preflight",
        status="operator_review_required",
        next_stage="stage2-observe",
        details={"ok": True},
    ).to_dict()
    payload["operator_confirmed"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PiKVMLiveValidationError, match="expected prior checkpoint"):
        validate_prior_checkpoint(path, expected_stage="stage2-observe")


def test_validate_prior_checkpoint_accepts_operator_confirmed(tmp_path) -> None:
    path = tmp_path / "stage1.json"
    payload = build_stage_checkpoint(
        stage="stage1-cert-pinning-preflight",
        status="operator_confirmed",
        next_stage="stage2-observe",
        details={"ok": True},
    ).to_dict()
    payload["operator_confirmed"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")

    checkpoint = validate_prior_checkpoint(
        path, expected_stage="stage1-cert-pinning-preflight"
    )

    assert checkpoint.operator_confirmed is True
    assert checkpoint.next_stage == "stage2-observe"


def test_deliberately_wrong_fingerprint_differs_but_stays_valid() -> None:
    normalized = normalize_cert_fingerprint(FAKE_FINGERPRINT)
    wrong = deliberately_wrong_fingerprint(FAKE_FINGERPRINT)

    assert wrong != normalized
    assert len(wrong) == len(normalized)
    # Normalized fingerprints are colon-separated lowercase hex pairs.
    assert set(wrong) <= set("0123456789abcdef:")
