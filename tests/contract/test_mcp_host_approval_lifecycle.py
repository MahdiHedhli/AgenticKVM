from datetime import UTC, datetime, timedelta

from agentickvm.mcp_sdk import (
    HostApprovalDecision,
    HostApprovalScope,
    MCPHostCompatibilityLayer,
    MCPSDKAdapter,
)
from agentickvm.control_plane import CapabilityRequest, ControlPlane
from agentickvm.mcp import MCPRouter, MCPToolRequest

NOW = datetime(2026, 6, 4, 1, 30, tzinfo=UTC)


def _dangerous_call(host: MCPHostCompatibilityLayer, *, params=None, target="mock-host"):
    return host.call_tool(
        {
            "tool_name": "force_restart",
            "target": target,
            "session_id": "host-session-1",
            "requester_id": "host-test",
            "params": params or {"reason": "test"},
            "correlation_id": "host-approval-force-restart",
        }
    )


def _approval_response(
    approval_result,
    *,
    decision=HostApprovalDecision.GRANTED,
    scope=HostApprovalScope.ONE_TIME,
    **overrides,
):
    approval = approval_result["approval_request"]
    return {
        "request_id": approval["id"],
        "decision": decision.value,
        "operator_id": "operator-1",
        "scope": scope.value,
        "decided_at": overrides.pop("decided_at", NOW.isoformat()),
        "session_id": overrides.pop("session_id", approval["session_id"]),
        "target": overrides.pop("target", approval["target"]),
        "provider": overrides.pop("provider", approval["provider"]),
        "capability": overrides.pop("capability", approval["capability"]),
        "params_fingerprint": overrides.pop(
            "params_fingerprint",
            approval["params_fingerprint"],
        ),
        **overrides,
    }


def _mock_provider(host: MCPHostCompatibilityLayer):
    return host.adapter.runtime.provider_registry.resolve_enabled("mock")


class SpyRouter(MCPRouter):
    handled: list[MCPToolRequest] = []

    def handle_tool_request(self, request: MCPToolRequest):
        self.handled.append(request)
        return super().handle_tool_request(request)


class SpyControlPlane(ControlPlane):
    handled: list[CapabilityRequest] = []

    def handle(self, request: CapabilityRequest):
        self.handled.append(request)
        return super().handle(request)


def test_host_one_time_approval_resumes_exactly_one_matching_mock_action() -> None:
    host = MCPHostCompatibilityLayer.mock_only()
    initial = _dangerous_call(host, params={"reason": "one-time"})
    assert initial["status"] == "approval_required"

    approval = host.submit_approval_response(_approval_response(initial))
    resumed = host.resume_approved_tool(initial["approval_request"]["id"])
    second = host.resume_approved_tool(initial["approval_request"]["id"])

    assert approval["status"] == "approval_granted"
    assert resumed["status"] == "ok"
    assert second["status"] == "approval_required"
    assert len(_mock_provider(host).requests) == 1


def test_host_approval_resumption_routes_through_router_and_control_plane() -> None:
    SpyRouter.handled = []
    SpyControlPlane.handled = []
    adapter = MCPSDKAdapter(
        router_factory=SpyRouter,
        control_plane_factory=SpyControlPlane,
    )
    host = MCPHostCompatibilityLayer(adapter=adapter)
    initial = _dangerous_call(host, params={"reason": "routing"})
    host.submit_approval_response(_approval_response(initial))

    resumed = host.resume_approved_tool(initial["approval_request"]["id"])

    assert resumed["status"] == "ok"
    assert [request.tool_name for request in SpyRouter.handled] == [
        "force_restart",
        "force_restart",
    ]
    assert [request.capability_id for request in SpyControlPlane.handled] == [
        "power.force_restart",
        "power.force_restart",
    ]


def test_host_session_approval_allows_matching_action_within_session() -> None:
    host = MCPHostCompatibilityLayer.mock_only()
    initial = _dangerous_call(host, params={"reason": "session"})
    host.submit_approval_response(
        _approval_response(initial, scope=HostApprovalScope.SESSION)
    )

    first = host.resume_approved_tool(initial["approval_request"]["id"])
    second = host.resume_approved_tool(initial["approval_request"]["id"])

    assert first["status"] == "ok"
    assert second["status"] == "ok"
    assert len(_mock_provider(host).requests) == 2


def test_host_approval_mismatch_fails_closed() -> None:
    host = MCPHostCompatibilityLayer.mock_only()
    initial = _dangerous_call(host)

    mismatch = host.submit_approval_response(
        _approval_response(initial, target="other-target")
    )
    resumed = host.resume_approved_tool(initial["approval_request"]["id"])

    assert mismatch["status"] == "validation_error"
    assert mismatch["reason"] == "approval target mismatch"
    assert resumed["status"] == "validation_error"
    assert _mock_provider(host).requests == []


def test_host_approval_cannot_approve_different_provider_capability_or_params() -> None:
    for override, expected in (
        ({"provider": "other-provider"}, "approval provider mismatch"),
        ({"capability": "power.graceful_restart"}, "approval capability mismatch"),
        ({"params_fingerprint": "different"}, "approval params_fingerprint mismatch"),
    ):
        host = MCPHostCompatibilityLayer.mock_only()
        initial = _dangerous_call(host)

        result = host.submit_approval_response(_approval_response(initial, **override))

        assert result["status"] == "validation_error"
        assert result["reason"] == expected
        assert _mock_provider(host).requests == []


def test_host_denied_approval_blocks_resumption() -> None:
    host = MCPHostCompatibilityLayer.mock_only()
    initial = _dangerous_call(host)

    denial = host.submit_approval_response(
        _approval_response(initial, decision=HostApprovalDecision.DENIED)
    )
    resumed = host.resume_approved_tool(initial["approval_request"]["id"])

    assert denial["status"] == "approval_denied"
    assert resumed["status"] == "validation_error"
    assert resumed["reason"] == "approval_denied"
    assert _mock_provider(host).requests == []


def test_host_expired_approval_blocks_resumption() -> None:
    host = MCPHostCompatibilityLayer.mock_only()
    initial = _dangerous_call(host)
    expired_at = datetime.fromisoformat(initial["approval_request"]["expires_at"])

    expired = host.submit_approval_response(
        _approval_response(
            initial,
            decided_at=(expired_at + timedelta(seconds=1)).isoformat(),
        )
    )
    resumed = host.resume_approved_tool(initial["approval_request"]["id"])

    assert expired["status"] == "approval_expired"
    assert resumed["status"] == "validation_error"
    assert resumed["reason"] == "approval_expired"
    assert _mock_provider(host).requests == []


def test_host_approval_cannot_approve_hard_invariant_actions() -> None:
    host = MCPHostCompatibilityLayer.mock_only()

    secret = host.call_tool(
        {
            "tool_name": "reveal_secret",
            "target": "mock-host",
            "session_id": "host-session-1",
            "requester_id": "host-test",
        }
    )
    policy = host.call_tool(
        {
            "tool_name": "modify_policy",
            "target": "mock-host",
            "session_id": "host-session-1",
            "requester_id": "host-test",
        }
    )
    fabricated = host.submit_approval_response(
        {
            "request_id": "fabricated-hard-invariant",
            "decision": "granted",
            "operator_id": "operator-1",
        }
    )

    assert secret["status"] == "denied"
    assert "approval_request" not in secret
    assert policy["status"] == "denied"
    assert "approval_request" not in policy
    assert fabricated["status"] == "validation_error"
    assert _mock_provider(host).requests == []
