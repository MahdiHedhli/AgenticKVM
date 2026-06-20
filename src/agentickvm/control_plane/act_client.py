"""Client seam for Agentic Control Tower clearance.

ACT is the source of truth for the canonical clearance request, response, and
proof format. These interfaces consume a client-side mirror aligned with the
published ``act.clearance.v2`` contract.
The mirror is not an AgenticKVM-owned wire contract.
The fail-closed ``ACTPendingProofVerifier`` remains the default until an operator
wires the real ``ACTClearanceProofVerifier`` (``act_proof``) and the real
``ACTHTTPClearanceClient`` (``act_http_client``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Mapping, Protocol

from agentickvm.control_plane.clearance import (
    AIRCRAFT_RISK_FAMILIES,
    ClearanceRequest,
    ClearanceResponse,
    ClearanceStatus,
    ClearanceVerificationResult,
)


class ClearanceClient(Protocol):
    """ACT clearance client interface."""

    def request_clearance(
        self,
        request: ClearanceRequest,
        *,
        timeout_seconds: int,
    ) -> ClearanceResponse:
        """Request clearance from ACT."""

    def deny_clearance(
        self,
        request_id: str,
        *,
        reason: str,
        timeout_seconds: int,
    ) -> ClearanceResponse:
        """Send a denial intent to ACT."""


class ClearanceProofVerifier(Protocol):
    """ACT clearance proof verification seam.

    ACT owns the real proof format. Implementations outside tests must fail
    closed until the canonical proof format is available.
    """

    def verify_proof(
        self,
        *,
        request: ClearanceRequest,
        response: ClearanceResponse,
    ) -> bool:
        """Return whether the ACT proof verifies for this request/response."""


@dataclass(frozen=True)
class ACTPendingProofVerifier:
    """Fail-closed verifier until ACT publishes the canonical proof format."""

    def verify_proof(
        self,
        *,
        request: ClearanceRequest,
        response: ClearanceResponse,
    ) -> bool:
        """Return false because the ACT proof format is not available yet."""

        return False


@dataclass(frozen=True)
class MockACTProofVerifier:
    """Test-only verifier for mock ACT responses."""

    def verify_proof(
        self,
        *,
        request: ClearanceRequest,
        response: ClearanceResponse,
    ) -> bool:
        """Verify the mock proof marker used in tests only."""

        return bool(response.proof and response.proof.get("mock_act_proof") == "verified")


@dataclass(frozen=True)
class ACTClearanceVerifier:
    """Verify an ACT clearance response as an AgenticKVM client."""

    tower_id: str
    proof_verifier: ClearanceProofVerifier = field(default_factory=ACTPendingProofVerifier)
    test_mode: bool = False

    def verify(
        self,
        *,
        request: ClearanceRequest,
        response: ClearanceResponse,
        now: datetime,
    ) -> ClearanceVerificationResult:
        """Verify a mirrored ACT clearance response for exact request binding."""

        base = {
            "tower_id": response.tower_id,
            "request_id": response.request_id,
        }
        if response.status != ClearanceStatus.CLEARED:
            return ClearanceVerificationResult(
                valid=False,
                status=response.status,
                reason=response.reason or "clearance is not cleared",
                **base,
            )
        if response.tower_id != self.tower_id:
            return ClearanceVerificationResult(
                valid=False,
                status=ClearanceStatus.VERIFICATION_FAILED,
                reason="tower identity mismatch",
                **base,
            )
        checks = {
            "request_id": (response.request_id, request.request_id),
            "session_id": (response.session_id, request.session_id),
            "target": (response.target, request.target),
            "provider": (response.provider, request.provider),
            "capability": (response.capability, request.capability),
            "params_fingerprint": (
                response.params_fingerprint,
                request.params_fingerprint,
            ),
            "short_code": (response.short_code, request.short_code),
            "audit_correlation_id": (
                response.audit_correlation_id,
                request.audit_correlation_id,
            ),
        }
        # ACT owns risk-family resolution and binds it cryptographically in the
        # proof. Only enforce request/response equality when ACT echoed the
        # aircraft's coarse family; a tower-resolved act.clearance.v2 family is
        # authoritative and is verified through the proof, not by string equality.
        if response.risk_family in AIRCRAFT_RISK_FAMILIES:
            checks["risk_family"] = (
                response.risk_family.value,
                request.risk_summary.risk_family.value,
            )
        mismatch = _first_mismatch(checks)
        if mismatch is not None:
            return ClearanceVerificationResult(
                valid=False,
                status=ClearanceStatus.VERIFICATION_FAILED,
                reason=f"{mismatch} mismatch",
                **base,
            )
        if response.expires_at is None:
            return ClearanceVerificationResult(
                valid=False,
                status=ClearanceStatus.VERIFICATION_FAILED,
                reason="clearance expiry is required",
                **base,
            )
        if now.astimezone(UTC) >= response.expires_at.astimezone(UTC):
            return ClearanceVerificationResult(
                valid=False,
                status=ClearanceStatus.EXPIRED,
                reason="clearance expired",
                **base,
            )
        if response.proof is None:
            return ClearanceVerificationResult(
                valid=False,
                status=ClearanceStatus.VERIFICATION_FAILED,
                reason="ACT clearance proof is required",
                **base,
            )
        if not self.test_mode and isinstance(self.proof_verifier, MockACTProofVerifier):
            return ClearanceVerificationResult(
                valid=False,
                status=ClearanceStatus.VERIFICATION_FAILED,
                reason="mock ACT proof verifier is test-only",
                **base,
            )
        if not self.proof_verifier.verify_proof(request=request, response=response):
            return ClearanceVerificationResult(
                valid=False,
                status=ClearanceStatus.VERIFICATION_FAILED,
                reason="ACT clearance proof verification failed",
                **base,
            )
        return ClearanceVerificationResult(
            valid=True,
            status=ClearanceStatus.CLEARED,
            reason="ACT clearance verified",
            **base,
        )


@dataclass
class MockACTClient:
    """Mock ACT client for CI and contract tests only."""

    default_status: ClearanceStatus = ClearanceStatus.CLEARANCE_REQUIRED
    tower_id: str = "mock-act"
    responses: dict[str, ClearanceResponse] = field(default_factory=dict)
    denials: dict[str, str] = field(default_factory=dict)

    def request_clearance(
        self,
        request: ClearanceRequest,
        *,
        timeout_seconds: int,
    ) -> ClearanceResponse:
        """Return a configured mock ACT response."""

        if request.request_id in self.responses:
            return self.responses[request.request_id]
        return ClearanceResponse(
            status=self.default_status,
            request_id=request.request_id,
            session_id=request.session_id,
            target=request.target,
            provider=request.provider,
            capability=request.capability,
            params_fingerprint=request.params_fingerprint,
            risk_family=request.risk_summary.risk_family,
            short_code=request.short_code,
            expires_at=request.expires_at,
            tower_id=self.tower_id,
            proof=(
                {"mock_act_proof": "verified"}
                if self.default_status == ClearanceStatus.CLEARED
                else None
            ),
            audit_correlation_id=request.audit_correlation_id,
            operator_message=request.operator_message,
            reason=self.default_status.value,
        )

    def deny_clearance(
        self,
        request_id: str,
        *,
        reason: str,
        timeout_seconds: int,
    ) -> ClearanceResponse:
        """Record a mock denial intent."""

        self.denials[request_id] = reason
        return ClearanceResponse(
            status=ClearanceStatus.DENIED,
            request_id=request_id,
            session_id="unknown",
            target="unknown",
            provider="unknown",
            capability="runtime.deny_clearance",
            params_fingerprint="unknown",
            risk_family="high_risk",
            short_code="UNKNOWN",
            tower_id=self.tower_id,
            reason=reason,
        )


def cleared_response_for(request: ClearanceRequest, *, tower_id: str = "mock-act") -> ClearanceResponse:
    """Build a test-only cleared response for a mirrored ACT request."""

    return ClearanceResponse(
        status=ClearanceStatus.CLEARED,
        request_id=request.request_id,
        session_id=request.session_id,
        target=request.target,
        provider=request.provider,
        capability=request.capability,
        params_fingerprint=request.params_fingerprint,
        risk_family=request.risk_summary.risk_family,
        short_code=request.short_code,
        expires_at=request.expires_at,
        tower_id=tower_id,
        proof={"mock_act_proof": "verified"},
        audit_correlation_id=request.audit_correlation_id,
        operator_message=request.operator_message,
        reason="mock cleared",
    )


def _first_mismatch(values: Mapping[str, tuple[str, str]]) -> str | None:
    for field_name, (actual, expected) in values.items():
        if actual != expected:
            return field_name
    return None
