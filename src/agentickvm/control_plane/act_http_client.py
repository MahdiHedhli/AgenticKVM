"""Real ACT clearance transport client.

This is the production replacement for ``MockACTClient``: it speaks the published
Agentic Control Tower gateway clearance endpoints
(``/hermes/tools/approval_requested`` and ``/hermes/tools/approval_status``) and
parses responses against the ``act.clearance.v2`` contract.

The HTTP transport is injected. The default ``UrllibACTHTTPTransport`` uses only
the standard library, but it is never exercised in CI -- automated tests inject a
deterministic transport, so no live network call is made. Live end-to-end
validation against a running tower (including params-fingerprint parity) is
operator-run, mirroring the supervised hardware validation harness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from agentickvm.control_plane.act_fingerprint import (
    act_agentickvm_extensions,
    act_params_fingerprint,
    act_short_code,
)
from agentickvm.control_plane.clearance import (
    ClearanceRequest,
    ClearanceResponse,
    ClearanceStatus,
    clearance_response_from_act_payload,
)

ACT_AIRCRAFT_AGENT_ID = "agentickvm"
APPROVAL_REQUESTED_PATH = "/hermes/tools/approval_requested"
APPROVAL_STATUS_PATH = "/hermes/tools/approval_status"


class ACTHTTPTransport(Protocol):
    """Minimal JSON-over-HTTP transport seam for the ACT gateway."""

    def post_json(
        self,
        path: str,
        body: Mapping[str, Any],
        *,
        timeout_seconds: int,
    ) -> Mapping[str, Any]:
        """POST a JSON body to ``path`` and return the decoded JSON response."""


@dataclass(frozen=True)
class UrllibACTHTTPTransport:
    """Standard-library HTTP transport for the ACT gateway (operator-run)."""

    base_url: str

    def post_json(
        self,
        path: str,
        body: Mapping[str, Any],
        *,
        timeout_seconds: int,
    ) -> Mapping[str, Any]:
        # Imported lazily so importing this module never implies network intent.
        from urllib import request as urllib_request

        url = self.base_url.rstrip("/") + path
        data = json.dumps(dict(body)).encode("utf-8")
        req = urllib_request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("ACT gateway returned a non-object response")
        return payload


def act_payload_redacted(request: ClearanceRequest) -> dict[str, Any]:
    """Return the redacted payload the aircraft sends (no raw parameters)."""

    return {"capability": request.capability}


def act_request_extensions(request: ClearanceRequest) -> dict[str, Any]:
    """Return the extensions envelope the aircraft sends to ACT."""

    return act_agentickvm_extensions(
        target=request.target,
        provider=request.provider,
        capability=request.capability,
        risk_summary=request.risk_summary.summary,
        policy_context=request.policy_context,
    )


def predicted_act_params_fingerprint(request: ClearanceRequest) -> str:
    """Predict the params_fingerprint ACT will compute for this request.

    ACT computes the fingerprint authoritatively from exactly the redacted
    payload and extensions the aircraft sends, so the aircraft can predict it to
    keep its clearance binding consistent with a live ACT response.
    """

    return act_params_fingerprint(
        payload_redacted=act_payload_redacted(request),
        extensions=act_request_extensions(request),
    )


def predicted_act_short_code(request: ClearanceRequest, *, approval_id: str | None = None) -> str:
    """Predict the operator short code ACT will derive for this request."""

    return act_short_code(
        approval_id or request.request_id,
        predicted_act_params_fingerprint(request),
    )


def clearance_request_to_act_payload(
    request: ClearanceRequest,
    *,
    agent_id: str,
    expires_in_seconds: int,
) -> dict[str, Any]:
    """Map the mirror clearance request to the published ACT request shape."""

    return {
        "requested_tool": request.capability,
        "capability": request.capability,
        "risk_level": "high" if request.risk_summary.risk_family.value == "high_risk" else "low",
        "risk_family": request.risk_summary.risk_family.value,
        "summary": request.risk_summary.summary,
        # No raw parameters cross this boundary; only the redacted shape does.
        "payload_redacted": act_payload_redacted(request),
        "agent_id": agent_id,
        "session_id": request.session_id,
        "expires_in_seconds": expires_in_seconds,
        "operator_message": str(request.operator_message),
        "short_code": str(request.short_code),
        "audit_correlation_id": request.audit_correlation_id,
        "request_id": request.request_id,
        "extensions": act_request_extensions(request),
    }


@dataclass(frozen=True)
class ACTHTTPClearanceClient:
    """ClearanceClient that consumes the real ACT gateway clearance contract."""

    transport: ACTHTTPTransport
    agent_id: str = ACT_AIRCRAFT_AGENT_ID
    extra_status_seconds: int = 30

    def request_clearance(
        self,
        request: ClearanceRequest,
        *,
        timeout_seconds: int,
    ) -> ClearanceResponse:
        payload = clearance_request_to_act_payload(
            request,
            agent_id=self.agent_id,
            expires_in_seconds=timeout_seconds + self.extra_status_seconds,
        )
        try:
            requested = self.transport.post_json(
                APPROVAL_REQUESTED_PATH, payload, timeout_seconds=timeout_seconds
            )
            approval_id = str(
                requested.get("approval_id")
                or requested.get("request_id")
                or request.request_id
            )
            status_payload = self.transport.post_json(
                APPROVAL_STATUS_PATH,
                {"approval_id": approval_id},
                timeout_seconds=timeout_seconds,
            )
            return clearance_response_from_act_payload(status_payload)
        except Exception:  # noqa: BLE001 - any transport/parse failure must fail closed.
            return self._unavailable(request)

    def deny_clearance(
        self,
        request_id: str,
        *,
        reason: str,
        timeout_seconds: int,
    ) -> ClearanceResponse:
        try:
            self.transport.post_json(
                APPROVAL_STATUS_PATH,
                {"approval_id": request_id, "intent": "deny", "reason": reason},
                timeout_seconds=timeout_seconds,
            )
        except Exception:  # noqa: BLE001
            pass
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
            reason=reason,
        )

    def _unavailable(self, request: ClearanceRequest) -> ClearanceResponse:
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


__all__ = [
    "ACT_AIRCRAFT_AGENT_ID",
    "APPROVAL_REQUESTED_PATH",
    "APPROVAL_STATUS_PATH",
    "ACTHTTPClearanceClient",
    "ACTHTTPTransport",
    "UrllibACTHTTPTransport",
    "act_payload_redacted",
    "act_request_extensions",
    "clearance_request_to_act_payload",
    "predicted_act_params_fingerprint",
    "predicted_act_short_code",
]
