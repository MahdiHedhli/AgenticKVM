"""Supervised PiKVM live validation helpers.

These helpers support operator-run manual validation. They are deliberately
outside the provider package so normal provider tests remain mock-only and
cannot accidentally open sockets.
"""

from __future__ import annotations

import json
import socket
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from agentickvm.providers.pikvm_transport import (
    LivePiKVMObserveTransport,
    PiKVMCredentialRef,
    PiKVMFingerprintMismatchError,
    PiKVMTargetConfig,
    PiKVMPinnedTrust,
    normalize_cert_fingerprint,
    sha256_fingerprint_for_der,
)


class PiKVMLiveValidationError(RuntimeError):
    """Raised when a live validation precondition or checkpoint is unsafe."""


@dataclass(frozen=True)
class ValidationPreconditions:
    """Operator-written preconditions required before any live stage."""

    sacrificial_target: str
    isolated_segment: str
    credential_ref: str
    firmware_version: str
    operator: str
    confirmed_at: str

    def __post_init__(self) -> None:
        values = {
            "sacrificial_target": self.sacrificial_target,
            "isolated_segment": self.isolated_segment,
            "credential_ref": self.credential_ref,
            "firmware_version": self.firmware_version,
            "operator": self.operator,
            "confirmed_at": self.confirmed_at,
        }
        missing = [key for key, value in values.items() if not value]
        if missing:
            raise PiKVMLiveValidationError(
                "missing live validation precondition fields: " + ", ".join(missing)
            )
        lowered_ref = self.credential_ref.lower()
        if any(fragment in lowered_ref for fragment in ("password=", "token=", "secret=")):
            raise PiKVMLiveValidationError("credential_ref must be a reference, not a raw secret")

    def to_dict(self) -> dict[str, str]:
        """Return JSON-safe preconditions without resolving credentials."""

        return {
            "sacrificial_target": self.sacrificial_target,
            "isolated_segment": self.isolated_segment,
            "credential_ref": "[CREDENTIAL_REF]",
            "firmware_version": self.firmware_version,
            "operator": self.operator,
            "confirmed_at": self.confirmed_at,
        }


@dataclass(frozen=True)
class StageCheckpoint:
    """One live validation stage result that requires human sign-off."""

    stage: str
    status: str
    operator_confirmed: bool
    next_stage: str | None
    details: Mapping[str, Any]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe checkpoint."""

        return {
            "stage": self.stage,
            "status": self.status,
            "operator_confirmed": self.operator_confirmed,
            "next_stage": self.next_stage,
            "details": dict(self.details),
            "generated_at": self.generated_at,
        }


class RealTLSPiKVMProbe:
    """Unauthenticated TLS probe for Stage 1 certificate fingerprint capture."""

    def certificate_der_sha256(
        self,
        *,
        host: str,
        port: int,
        timeout_seconds: float,
    ) -> str:
        """Return the peer certificate SHA-256 fingerprint without credentials."""

        context = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout_seconds) as sock:
            with context.wrap_socket(sock, server_hostname=host) as tls:
                cert_der = tls.getpeercert(binary_form=True)
        if not cert_der:
            raise PiKVMLiveValidationError("PiKVM peer did not present a certificate")
        return sha256_fingerprint_for_der(cert_der)


class _RecordingAuthenticatedHTTPClient:
    """Client built by Stage 1 only; it never sends HTTP requests."""

    def __init__(self, trust: PiKVMPinnedTrust | None) -> None:
        self.trust = trust

    def get_json(self, path: str, *, timeout_seconds: float) -> Mapping[str, Any]:
        raise PiKVMLiveValidationError(
            "Stage 1 validates authenticated-client construction only; observe runs in Stage 2"
        )


class _RecordingHTTPClientFactory:
    """Record whether credentials would have been handed to an authenticated client."""

    def __init__(self) -> None:
        self.credential_ref_received = False
        self.trust_received: PiKVMPinnedTrust | None = None

    def __call__(
        self,
        config: PiKVMTargetConfig,
        credential_ref: PiKVMCredentialRef,
        trust: PiKVMPinnedTrust | None,
    ) -> _RecordingAuthenticatedHTTPClient:
        self.credential_ref_received = True
        self.trust_received = trust
        return _RecordingAuthenticatedHTTPClient(trust)


def load_preconditions(path: str | Path) -> ValidationPreconditions:
    """Load operator-written JSON preconditions from an explicit path."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise PiKVMLiveValidationError("preconditions file must contain a JSON object")
    return ValidationPreconditions(
        sacrificial_target=str(payload.get("sacrificial_target", "")),
        isolated_segment=str(payload.get("isolated_segment", "")),
        credential_ref=str(payload.get("credential_ref", "")),
        firmware_version=str(payload.get("firmware_version", "")),
        operator=str(payload.get("operator", "")),
        confirmed_at=str(payload.get("confirmed_at", "")),
    )


def run_stage1_cert_preflight(
    *,
    base_url: str,
    credential_ref: str,
    cert_fingerprint: str | None,
    verify_ssl: bool,
    tls_probe: Any,
) -> StageCheckpoint:
    """Run Stage 1 certificate capture and pinning checks.

    The only real network operation is the unauthenticated TLS certificate
    probe. Credentials are never resolved and are never passed on the mismatch
    path.
    """

    capture_config = PiKVMTargetConfig(
        base_url=base_url,
        cert_fingerprint=cert_fingerprint,
        verify_ssl=verify_ssl,
    )
    observed = tls_probe.certificate_der_sha256(
        host=capture_config.host,
        port=capture_config.port,
        timeout_seconds=capture_config.connect_timeout_seconds,
    )
    details: dict[str, Any] = {
        "observed_cert_fingerprint": observed,
        "credential_ref": "[CREDENTIAL_REF]",
        "verify_ssl_false_without_pin_rejected": _verify_ssl_false_without_pin_rejected(
            base_url
        ),
    }
    if cert_fingerprint:
        normalized = normalize_cert_fingerprint(cert_fingerprint)
        match_factory = _RecordingHTTPClientFactory()
        LivePiKVMObserveTransport(
            config=PiKVMTargetConfig(
                base_url=base_url,
                cert_fingerprint=normalized,
                verify_ssl=verify_ssl,
            ),
            credential_ref=PiKVMCredentialRef(credential_ref),
            tls_probe=tls_probe,
            http_client_factory=match_factory,
        )
        details["pinned_match_built_authenticated_client"] = (
            match_factory.credential_ref_received
            and match_factory.trust_received is not None
            and match_factory.trust_received.sha256_fingerprint == normalized
        )

        mismatch_factory = _RecordingHTTPClientFactory()
        try:
            LivePiKVMObserveTransport(
                config=PiKVMTargetConfig(
                    base_url=base_url,
                    cert_fingerprint=deliberately_wrong_fingerprint(normalized),
                    verify_ssl=verify_ssl,
                ),
                credential_ref=PiKVMCredentialRef(credential_ref),
                tls_probe=tls_probe,
                http_client_factory=mismatch_factory,
            )
        except PiKVMFingerprintMismatchError:
            details["wrong_fingerprint_aborted_before_credentials"] = (
                mismatch_factory.credential_ref_received is False
            )
        else:
            details["wrong_fingerprint_aborted_before_credentials"] = False
    return build_stage_checkpoint(
        stage="stage1-cert-pinning-preflight",
        status="operator_review_required",
        next_stage="stage2-observe",
        details=details,
    )


def build_stage_checkpoint(
    *,
    stage: str,
    status: str,
    next_stage: str | None,
    details: Mapping[str, Any],
) -> StageCheckpoint:
    """Build a checkpoint that never auto-confirms operator review."""

    return StageCheckpoint(
        stage=stage,
        status=status,
        operator_confirmed=False,
        next_stage=next_stage,
        details=MappingProxyType(dict(details)),
        generated_at=datetime.now(UTC).isoformat(),
    )


def validate_prior_checkpoint(
    path: str | Path,
    *,
    expected_stage: str,
) -> StageCheckpoint:
    """Require explicit operator confirmation from a previous stage."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise PiKVMLiveValidationError("checkpoint file must contain a JSON object")
    stage = str(payload.get("stage", ""))
    if stage != expected_stage:
        raise PiKVMLiveValidationError(f"expected prior checkpoint {expected_stage}, got {stage}")
    if payload.get("operator_confirmed") is not True:
        raise PiKVMLiveValidationError(
            f"operator must confirm {expected_stage} before advancing"
        )
    return StageCheckpoint(
        stage=stage,
        status=str(payload.get("status", "")),
        operator_confirmed=True,
        next_stage=payload.get("next_stage") if payload.get("next_stage") else None,
        details=MappingProxyType(dict(payload.get("details", {}))),
        generated_at=str(payload.get("generated_at", "")),
    )


def deliberately_wrong_fingerprint(fingerprint: str) -> str:
    """Return a valid SHA-256 fingerprint that cannot equal the input."""

    normalized = normalize_cert_fingerprint(fingerprint)
    first = "00" if not normalized.startswith("00") else "ff"
    return first + normalized[2:]


def _verify_ssl_false_without_pin_rejected(base_url: str) -> bool:
    try:
        PiKVMTargetConfig(
            base_url=base_url,
            cert_fingerprint=None,
            verify_ssl=False,
        )
    except Exception:
        return True
    return False
