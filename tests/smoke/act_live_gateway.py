"""Live scratch-gateway harness for the clearance-chain smoke suite.

Gateway-live mode is opt-in: set ``AGENTICKVM_ACT_LIVE_GATEWAY_URL`` to a
scratch Agentic Control Tower gateway on localhost (for example
``http://127.0.0.1:8905``). Without it, every gateway-dependent smoke case
skips with a named reason. The only network this harness ever touches is that
operator-provided localhost gateway; no hardware, no external hosts, and no
credential material beyond throwaway in-memory device keys generated per run.

The harness plays both ends of the beta contract:

- the operator's paired mobile device (Ed25519 pairing + HMCP-signed decision,
  intervention, and audit-read requests), and
- the aircraft's clearance legs against the tower's converged clearance seam
  (``/v1/approvals`` creation with the full extensions envelope +
  ``/v1/hermes/tools/approval_status`` polling), reusing the production
  ``UrllibACTHTTPTransport`` and the production response parser/verifiers.

The Ed25519 signing primitives below reuse the vendored RFC 8032 curve
arithmetic from ``agentickvm.control_plane.act_proof`` (which only verifies)
to sign; they exist so the smoke suite needs no third-party crypto dependency.
Keys are throwaway test identities, never persisted.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from base64 import urlsafe_b64encode
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping

import pytest

from agentickvm.control_plane.act_client import ACTClearanceVerifier
from agentickvm.control_plane.act_http_client import (
    ACT_AIRCRAFT_AGENT_ID,
    APPROVAL_STATUS_PATH,
    UrllibACTHTTPTransport,
    act_payload_redacted,
    act_request_extensions,
    act_wire_risk_family,
)
from agentickvm.control_plane.act_proof import (
    ACTClearanceProofVerifier,
    TowerKeyRegistry,
    _B,  # vendored RFC 8032 base point (curve arithmetic reused for signing)
    _scalarmult,
)
from agentickvm.control_plane.clearance import (
    ClearanceRequest,
    ClearanceResponse,
    ClearanceRiskFamily,
    ClearanceStatus,
    clearance_response_from_act_payload,
)

LIVE_GATEWAY_URL_ENV = "AGENTICKVM_ACT_LIVE_GATEWAY_URL"
LIVE_TOWER_ID_ENV = "AGENTICKVM_ACT_LIVE_TOWER_ID"
LIVE_TOWER_FINGERPRINT_ENV = "AGENTICKVM_ACT_LIVE_TOWER_FINGERPRINT"

# Defaults match the scratch gateway's own defaults (Settings.node_id /
# Settings.node_fingerprint) so only the URL is required for a local run.
DEFAULT_LIVE_TOWER_ID = "node_local"
DEFAULT_LIVE_TOWER_FINGERPRINT = "local-dev-fingerprint"

LIVE_GATEWAY_SKIP_REASON = (
    "gateway-live mode only: set AGENTICKVM_ACT_LIVE_GATEWAY_URL to a scratch "
    "ACT gateway on localhost (e.g. http://127.0.0.1:8905) to run the "
    "clearance-chain smoke cases against a real converged tower"
)

requires_live_gateway = pytest.mark.skipif(
    not os.environ.get(LIVE_GATEWAY_URL_ENV),
    reason=LIVE_GATEWAY_SKIP_REASON,
)

# Ed25519 group order (RFC 8032).
_GROUP_ORDER = 2**252 + 27742317777372353535851937790883648493


def live_gateway_api_base() -> str:
    """Return the live gateway ``/v1`` API base URL from the environment."""

    url = os.environ.get(LIVE_GATEWAY_URL_ENV, "").rstrip("/")
    if not url:
        raise RuntimeError(LIVE_GATEWAY_SKIP_REASON)
    return url if url.endswith("/v1") else url + "/v1"


def live_tower_id() -> str:
    return os.environ.get(LIVE_TOWER_ID_ENV) or DEFAULT_LIVE_TOWER_ID


def live_tower_fingerprint() -> str:
    return os.environ.get(LIVE_TOWER_FINGERPRINT_ENV) or DEFAULT_LIVE_TOWER_FINGERPRINT


# --------------------------------------------------------------------------- #
# Minimal Ed25519 signing on top of the vendored verification arithmetic
# --------------------------------------------------------------------------- #


def _encode_point(point: tuple[int, int]) -> bytes:
    x, y = point
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _clamped_scalar(seed: bytes) -> tuple[int, bytes]:
    digest = hashlib.sha512(seed).digest()
    scalar = int.from_bytes(digest[:32], "little")
    scalar &= (1 << 254) - 8
    scalar |= 1 << 254
    return scalar, digest[32:]


def ed25519_public_key(seed: bytes) -> bytes:
    """Derive the 32-byte Ed25519 public key for a 32-byte seed."""

    scalar, _ = _clamped_scalar(seed)
    return _encode_point(_scalarmult(_B, scalar))


def ed25519_sign(seed: bytes, message: bytes) -> bytes:
    """Produce an RFC 8032 Ed25519 signature (test-harness signing only)."""

    scalar, prefix = _clamped_scalar(seed)
    public = _encode_point(_scalarmult(_B, scalar))
    nonce = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % _GROUP_ORDER
    big_r = _encode_point(_scalarmult(_B, nonce))
    challenge = (
        int.from_bytes(hashlib.sha512(big_r + public + message).digest(), "little")
        % _GROUP_ORDER
    )
    s_value = (nonce + challenge * scalar) % _GROUP_ORDER
    return big_r + s_value.to_bytes(32, "little")


def b64url(value: bytes) -> str:
    return urlsafe_b64encode(value).decode("ascii").rstrip("=")


def derive_tower_key_registry(*, tower_id: str, node_fingerprint: str) -> TowerKeyRegistry:
    """Derive the scratch tower's Ed25519 proof public key.

    The gateway derives its proof signing key deterministically from its node
    fingerprint (``sha256("act-tower-proof:" + node_fingerprint)``), so a
    smoke run against a scratch tower can pin the exact tower key without any
    out-of-band key exchange.
    """

    seed = hashlib.sha256(f"act-tower-proof:{node_fingerprint}".encode("utf-8")).digest()
    return TowerKeyRegistry(keys={f"tower:{tower_id}": ed25519_public_key(seed)})


def live_tower_clearance_verifier() -> ACTClearanceVerifier:
    """Build the strict production verifier pinned to the scratch tower."""

    registry = derive_tower_key_registry(
        tower_id=live_tower_id(), node_fingerprint=live_tower_fingerprint()
    )
    return ACTClearanceVerifier(
        tower_id=live_tower_id(),
        proof_verifier=ACTClearanceProofVerifier(registry=registry),
    )


# --------------------------------------------------------------------------- #
# HTTP helpers (localhost scratch gateway only)
# --------------------------------------------------------------------------- #


def _http_json(
    method: str,
    url: str,
    body: Mapping[str, Any] | None,
    headers: Mapping[str, str] | None = None,
    timeout_seconds: int = 10,
) -> tuple[int, dict[str, Any]]:
    data = (
        json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
        if body is not None
        else None
    )
    request = urllib.request.Request(
        url, data=data, headers=dict(headers or {}), method=method
    )
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            return int(response.status), json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        return int(exc.code), json.loads(exc.read() or b"{}")


@dataclass
class GatewayOperator:
    """The operator side of the chain: a paired device with signing keys."""

    api_base: str
    device_id: str
    seed: bytes = field(repr=False)

    @classmethod
    def pair(cls, api_base: str, *, display_name: str = "KVM Smoke Operator") -> "GatewayOperator":
        """Pair a fresh throwaway operator device against the scratch tower."""

        seed = hashlib.sha256(f"agentickvm-smoke-operator:{time.time_ns()}".encode()).digest()
        status, pairing = _http_json(
            "POST",
            api_base + "/pairing/start",
            {
                "display_name": display_name,
                "requested_permissions": ["read_state", "approve", "intervene"],
                "clearance_channel": "mobile_signed",
            },
        )
        assert status == 201, f"pairing/start failed: {status} {pairing}"
        status, paired = _http_json(
            "POST",
            api_base + "/pairing/complete",
            {
                "pairing_id": pairing["pairing_id"],
                "challenge_response": pairing["pairing_token"],
                "device_public_key": b64url(ed25519_public_key(seed)),
                "device": {
                    "device_name": display_name,
                    "platform": "ios",
                    "app_instance_id": "agentickvm-smoke-suite",
                    "app_version": "0.0.0",
                },
            },
        )
        assert status == 200, f"pairing/complete failed: {status} {paired}"
        return cls(api_base=api_base, device_id=paired["device"]["device_id"], seed=seed)

    def signed(
        self, method: str, path: str, body: Mapping[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]:
        """Send an HMCP-signed operator request (path is relative to /v1)."""

        body_bytes = (
            json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
            if body is not None
            else b""
        )
        signed_path = "/v1" + path
        timestamp = str(int(time.time()))
        nonce = f"nonce-{time.time_ns()}"
        canonical = "\n".join(
            [
                "HMCP-SIGN-V1",
                method.upper(),
                signed_path,
                timestamp,
                nonce,
                hashlib.sha256(body_bytes).hexdigest(),
            ]
        )
        headers = {
            "X-HMCP-Device-Id": self.device_id,
            "X-HMCP-Timestamp": timestamp,
            "X-HMCP-Nonce": nonce,
            "X-HMCP-Signature": b64url(ed25519_sign(self.seed, canonical.encode("utf-8"))),
        }
        return _http_json(method, self.api_base + path, body, headers=headers)

    def approve_once(self, approval_id: str) -> dict[str, Any]:
        status, decision = self.signed("POST", f"/approvals/{approval_id}/approve_once")
        assert status == 200, f"approve_once failed: {status} {decision}"
        return decision

    def deny(self, approval_id: str) -> dict[str, Any]:
        status, decision = self.signed("POST", f"/approvals/{approval_id}/deny")
        assert status == 200, f"deny failed: {status} {decision}"
        return decision

    def emergency_stop(self, session_id: str, *, reason: str) -> dict[str, Any]:
        status, result = self.signed(
            "POST",
            f"/sessions/{session_id}/interventions",
            {
                "intervention_id": f"int_smoke_{time.time_ns()}",
                "type": "emergency_stop",
                "reason": reason,
                "signed_payload": {"type": "emergency_stop"},
                "signature": "sig_smoke_test",
            },
        )
        assert status == 200, f"emergency_stop failed: {status} {result}"
        return result

    def audit_events(self, event_type: str) -> list[dict[str, Any]]:
        status, payload = self.signed("GET", f"/audit/events?event_type={event_type}")
        assert status == 200, f"audit read failed: {status} {payload}"
        return list(payload.get("audit_events", []))


# --------------------------------------------------------------------------- #
# Aircraft-side clearance client against the converged tower seam
# --------------------------------------------------------------------------- #


class ConvergedTowerClearanceClient:
    """ClearanceClient for the converged tower's full-fidelity clearance seam.

    Resume-first: an incoming request whose ``request_id`` already names a
    tower approval polls its status; anything unknown files a new clearance
    request through ``/v1/approvals`` with the aircraft's complete redacted
    payload + extensions envelope (the same bytes the ACT-parity fingerprint
    prediction covers), then polls once. Every transport or parse failure
    fails closed as ``TOWER_UNAVAILABLE``.
    """

    def __init__(self, api_base: str, *, agent_id: str = ACT_AIRCRAFT_AGENT_ID) -> None:
        self.transport = UrllibACTHTTPTransport(base_url=api_base)
        self.agent_id = agent_id

    def request_clearance(
        self, request: ClearanceRequest, *, timeout_seconds: int
    ) -> ClearanceResponse:
        try:
            payload = self.poll_raw(request.request_id, timeout_seconds=timeout_seconds)
            if payload is None:
                created = self.transport.post_json(
                    "/approvals",
                    self._create_body(request),
                    timeout_seconds=timeout_seconds,
                )
                approval_id = str(created.get("approval_id") or request.request_id)
                payload = self.poll_raw(approval_id, timeout_seconds=timeout_seconds)
                if payload is None:
                    raise ValueError("tower lost the approval it just created")
            return clearance_response_from_act_payload(payload)
        except Exception:  # noqa: BLE001 - fail closed on any transport/parse gap.
            return ClearanceResponse(
                status=ClearanceStatus.TOWER_UNAVAILABLE,
                request_id=request.request_id,
                session_id=request.session_id,
                target=request.target,
                provider=request.provider,
                capability=request.capability,
                params_fingerprint=request.params_fingerprint,
                risk_family=request.risk_summary.risk_family,
                short_code=request.short_code,
                reason="ACT gateway unavailable or returned an unparseable response",
            )

    def deny_clearance(
        self, request_id: str, *, reason: str, timeout_seconds: int
    ) -> ClearanceResponse:
        return ClearanceResponse(
            status=ClearanceStatus.DENIED,
            request_id=request_id,
            session_id="unknown",
            target="unknown",
            provider="unknown",
            capability="runtime.deny_clearance",
            params_fingerprint="unknown",
            risk_family=ClearanceRiskFamily.HIGH_RISK,
            short_code="UNKNOWN",
            reason=reason,
        )

    def poll_raw(self, approval_id: str, *, timeout_seconds: int) -> Mapping[str, Any] | None:
        """Return the raw status payload for an approval, or None if unknown."""

        try:
            return self.transport.post_json(
                APPROVAL_STATUS_PATH,
                {"approval_id": approval_id},
                timeout_seconds=timeout_seconds,
            )
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise

    def _create_body(self, request: ClearanceRequest) -> dict[str, Any]:
        return {
            "action_id": request.request_id,
            "agent_id": self.agent_id,
            "session_id": request.session_id,
            "requested_tool": request.capability,
            "capability": request.capability,
            "risk_level": (
                "high" if request.risk_summary.risk_family.value == "high_risk" else "low"
            ),
            "risk_family": act_wire_risk_family(request.risk_summary.risk_family.value),
            "summary": request.risk_summary.summary,
            # Only the redacted shape crosses this boundary, exactly the bytes
            # covered by the ACT-parity fingerprint prediction.
            "full_payload_redacted": act_payload_redacted(request),
            "extensions": act_request_extensions(request),
            "audit_correlation_id": request.audit_correlation_id,
            "operator_message": str(request.operator_message),
            "options": ["approve_once", "deny"],
            "expires_at": request.expires_at.astimezone(UTC).isoformat(),
        }


def utc_now() -> datetime:
    return datetime.now(UTC)
