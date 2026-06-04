import json
from datetime import UTC, datetime, timedelta

import pytest

from agentickvm.mcp_sdk import (
    HostApprovalDecision,
    HostApprovalRequest,
    HostApprovalResponse,
    HostApprovalResult,
    HostApprovalResultStatus,
    HostApprovalScope,
    approval_fingerprint,
)

NOW = datetime(2026, 6, 4, 1, 0, tzinfo=UTC)


def _approval_result(params=None):
    params = params or {"reason": "test"}
    return {
        "status": "approval_required",
        "tool_name": "force_restart",
        "capability": "power.force_restart",
        "target": "mock-host",
        "provider": "mock",
        "reason": "operator approval required",
        "data": {
            "params_preview": params,
            "params_fingerprint": approval_fingerprint(params),
            "policy_decision": "ask_each_time",
            "approval_request": {
                "id": "approval-1",
                "created_at": NOW.isoformat(),
                "expires_at": (NOW + timedelta(minutes=15)).isoformat(),
                "session_id": "s1",
                "requester": {"type": "agent", "id": "agent-1"},
                "capability": {
                    "id": "power.force_restart",
                    "family": "power",
                    "action": "force_restart",
                },
                "target_scope": {"targets": ["mock-host"], "allow_real_hardware": False},
                "provider_id": "mock",
                "policy_decision": "ask_each_time",
                "operator_message": "agent-1 requests power.force_restart",
                "material_risks": ["dangerous action"],
                "proposed_audit_event_id": "audit-1",
            },
        },
        "approval_request_id": "approval-1",
        "risks": ["dangerous action"],
        "redactions": [],
    }


def test_host_approval_request_serializes_safely() -> None:
    approval = HostApprovalRequest.from_host_result(
        _approval_result({"password": "must-not-leak-host-secret"}),
        params={"password": "must-not-leak-host-secret"},
        correlation_id="corr-1",
    )

    payload = approval.to_dict()

    assert payload["id"] == "approval-1"
    assert payload["target"] == "mock-host"
    assert payload["provider"] == "mock"
    assert payload["capability"] == "power.force_restart"
    assert payload["params_preview"]["password"] == "[REDACTED]"
    assert "must-not-leak-host-secret" not in repr(payload)
    assert "one_time" in payload["scope_options"]
    assert "session" in payload["scope_options"]
    json.dumps(payload)


def test_host_approval_response_serializes_safely() -> None:
    response = HostApprovalResponse(
        request_id="approval-1",
        decision=HostApprovalDecision.GRANTED,
        operator_id="operator-1",
        scope=HostApprovalScope.ONE_TIME,
        reason="token must-not-leak-host-secret",
        decided_at=NOW,
        session_id="s1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        params_fingerprint=approval_fingerprint({"reason": "test"}),
    )

    payload = response.to_dict()

    assert payload["decision"] == "granted"
    assert payload["scope"] == "one_time"
    assert payload["reason"] == "[REDACTED]"
    assert "must-not-leak-host-secret" not in repr(payload)
    json.dumps(payload)


def test_approval_fingerprint_is_stable_and_materially_sensitive() -> None:
    first = approval_fingerprint({"a": 1, "b": ["x", "y"]})
    second = approval_fingerprint({"b": ["x", "y"], "a": 1})
    different = approval_fingerprint({"a": 1, "b": ["x", "z"]})

    assert first == second
    assert first != different


def test_expired_approval_request_serializes_with_expiry() -> None:
    approval = HostApprovalRequest(
        id="approval-expired",
        session_id="s1",
        target="mock-host",
        provider="mock",
        capability="power.force_restart",
        params_fingerprint=approval_fingerprint({}),
        expires_at=NOW - timedelta(seconds=1),
        policy_decision="ask_each_time",
        operator_message="approval expired",
    )

    payload = approval.to_dict()

    assert payload["expires_at"] == (NOW - timedelta(seconds=1)).isoformat()
    json.dumps(payload)


def test_denial_result_serializes_safely() -> None:
    response = HostApprovalResponse(
        request_id="approval-1",
        decision=HostApprovalDecision.DENIED,
        operator_id="operator-1",
        reason="do not run",
        decided_at=NOW,
    )
    result = HostApprovalResult(
        status=HostApprovalResultStatus.DENIED,
        request_id="approval-1",
        reason="approval denied",
        response=response,
        grant={"session_cookie": "must-not-leak-host-secret"},
    )

    payload = result.to_dict()

    assert payload["status"] == "approval_denied"
    assert payload["grant"]["session_cookie"] == "[REDACTED]"
    assert "must-not-leak-host-secret" not in repr(payload)
    json.dumps(payload)


def test_malformed_approval_response_fails_closed() -> None:
    with pytest.raises(ValueError, match="approval request_id is required"):
        HostApprovalResponse.from_mapping(
            {
                "decision": "granted",
                "operator_id": "operator-1",
            }
        )

    with pytest.raises(ValueError):
        HostApprovalResponse.from_mapping(
            {
                "request_id": "approval-1",
                "decision": "maybe",
                "operator_id": "operator-1",
            }
        )
