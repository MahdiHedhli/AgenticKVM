from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agentickvm.live_validation.pikvm import (
    PiKVMLiveValidationError,
    deliberately_wrong_fingerprint,
    load_preconditions,
    run_stage1_cert_preflight,
    validate_prior_checkpoint,
)
from agentickvm.providers.pikvm_transport import normalize_cert_fingerprint


ROOT = Path(__file__).resolve().parents[2]
GOOD_FINGERPRINT = "aa" * 32


class MockTLSProbe:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint
        self.calls: list[dict[str, object]] = []

    def certificate_der_sha256(
        self,
        *,
        host: str,
        port: int,
        timeout_seconds: float,
    ) -> str:
        self.calls.append({"host": host, "port": port, "timeout_seconds": timeout_seconds})
        return self.fingerprint


def test_preconditions_template_and_loader_require_written_operator_facts(tmp_path: Path) -> None:
    template_path = tmp_path / "preconditions.json"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "pikvm-live-validation.py"),
            "preconditions-template",
            "--output",
            str(template_path),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert result.returncode == 0
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    assert "sacrificial_target" in payload
    payload.update(
        {
            "sacrificial_target": "sacrificial lab host",
            "isolated_segment": "isolated validation VLAN",
            "credential_ref": "keychain://pikvm/validation",
            "firmware_version": "PiKVM fixture-version-record",
            "operator": "human",
            "confirmed_at": "2026-06-15T12:00:00Z",
        }
    )
    template_path.write_text(json.dumps(payload), encoding="utf-8")

    preconditions = load_preconditions(template_path)

    assert preconditions.to_dict()["credential_ref"] == "[CREDENTIAL_REF]"
    assert "keychain://pikvm/validation" not in repr(preconditions.to_dict())


def test_preconditions_reject_raw_secret_shaped_credential_refs(tmp_path: Path) -> None:
    preconditions_path = tmp_path / "preconditions.json"
    preconditions_path.write_text(
        json.dumps(
            {
                "sacrificial_target": "sacrificial lab host",
                "isolated_segment": "isolated validation VLAN",
                "credential_ref": "password=synthetic-secret",
                "firmware_version": "PiKVM fixture-version-record",
                "operator": "human",
                "confirmed_at": "2026-06-15T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(PiKVMLiveValidationError, match="credential_ref"):
        load_preconditions(preconditions_path)


def test_stage1_mock_preflight_proves_wrong_pin_aborts_before_credentials() -> None:
    probe = MockTLSProbe(normalize_cert_fingerprint(GOOD_FINGERPRINT))

    checkpoint = run_stage1_cert_preflight(
        base_url="https://pikvm.example.invalid",
        credential_ref="keychain://pikvm/validation",
        cert_fingerprint=GOOD_FINGERPRINT,
        verify_ssl=False,
        tls_probe=probe,
    )

    assert checkpoint.stage == "stage1-cert-pinning-preflight"
    assert checkpoint.operator_confirmed is False
    assert checkpoint.next_stage == "stage2-observe"
    assert checkpoint.details["pinned_match_built_authenticated_client"] is True
    assert checkpoint.details["wrong_fingerprint_aborted_before_credentials"] is True
    assert checkpoint.details["verify_ssl_false_without_pin_rejected"] is True
    assert checkpoint.details["credential_ref"] == "[CREDENTIAL_REF]"
    assert probe.calls


def test_deliberately_wrong_fingerprint_remains_valid_and_different() -> None:
    wrong = deliberately_wrong_fingerprint(GOOD_FINGERPRINT)

    assert normalize_cert_fingerprint(wrong) == wrong
    assert wrong != normalize_cert_fingerprint(GOOD_FINGERPRINT)


def test_checkpoint_must_be_operator_confirmed_before_next_stage(tmp_path: Path) -> None:
    checkpoint_path = tmp_path / "stage1.json"
    checkpoint = {
        "stage": "stage1-cert-pinning-preflight",
        "status": "operator_review_required",
        "operator_confirmed": False,
        "next_stage": "stage2-observe",
        "details": {},
        "generated_at": "2026-06-15T12:00:00Z",
    }
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")

    with pytest.raises(PiKVMLiveValidationError, match="operator must confirm"):
        validate_prior_checkpoint(
            checkpoint_path,
            expected_stage="stage1-cert-pinning-preflight",
        )

    checkpoint["operator_confirmed"] = True
    checkpoint_path.write_text(json.dumps(checkpoint), encoding="utf-8")
    confirmed = validate_prior_checkpoint(
        checkpoint_path,
        expected_stage="stage1-cert-pinning-preflight",
    )

    assert confirmed.operator_confirmed is True


def test_stage2_script_refuses_unconfirmed_prior_checkpoint(tmp_path: Path) -> None:
    preconditions_path = tmp_path / "preconditions.json"
    preconditions_path.write_text(
        json.dumps(
            {
                "sacrificial_target": "sacrificial lab host",
                "isolated_segment": "isolated validation VLAN",
                "credential_ref": "keychain://pikvm/validation",
                "firmware_version": "PiKVM fixture-version-record",
                "operator": "human",
                "confirmed_at": "2026-06-15T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    checkpoint_path = tmp_path / "stage1.json"
    checkpoint_path.write_text(
        json.dumps(
            {
                "stage": "stage1-cert-pinning-preflight",
                "status": "operator_review_required",
                "operator_confirmed": False,
                "next_stage": "stage2-observe",
                "details": {},
                "generated_at": "2026-06-15T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "pikvm-live-validation.py"),
            "stage2-observe",
            "--preconditions",
            str(preconditions_path),
            "--previous-checkpoint",
            str(checkpoint_path),
            "--output",
            str(tmp_path / "stage2.json"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    assert result.returncode == 2
    assert "operator must confirm" in result.stdout
