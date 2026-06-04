"""Mock-only MCP host compatibility adapter.

This module provides a local, dependency-free compatibility boundary for
future MCP host behavior. It does not open listeners, import a live SDK, resolve
credentials, or execute providers directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from agentickvm.config import ConfigRuntime, build_runtime, load_config
from agentickvm.control_plane import (
    Actor,
    ActorType,
    ApprovalGrant,
    ApprovalGrantScope,
    ApprovalStore,
    AuditEventType,
    CapabilityRef,
    DEFAULT_CAPABILITY_REGISTRY,
    LocalJSONLAuditSink,
    PolicyDecision,
    build_audit_event,
)
from agentickvm.control_plane.audit import AuditSink
from agentickvm.mcp_sdk.approval_models import (
    HostApprovalDecision,
    HostApprovalRequest,
    HostApprovalResponse,
    HostApprovalResult,
    HostApprovalResultStatus,
)
from agentickvm.mcp_sdk.adapter import MCPSDKAdapter
from agentickvm.mcp_sdk.host_models import (
    HostError,
    HostResultStatus,
    HostToolCall,
    HostToolDescriptor,
    HostToolResult,
    HostToolSchema,
)
from agentickvm.mcp_sdk.models import MCPSDKToolCall


@dataclass(frozen=True)
class _PendingApproval:
    call: HostToolCall
    approval: HostApprovalRequest


class MCPHostCompatibilityLayer:
    """Local host compatibility layer over the mock-only SDK adapter."""

    def __init__(
        self,
        *,
        adapter: MCPSDKAdapter | None = None,
        runtime: ConfigRuntime | None = None,
        config_path: str | None = None,
        audit_path: str | Path | None = None,
        now_factory: Any | None = None,
        adapter_factory: type[MCPSDKAdapter] = MCPSDKAdapter,
    ) -> None:
        if adapter is not None and (runtime is not None or config_path is not None):
            raise ValueError("provide either adapter or runtime/config_path, not both")
        if adapter is not None and audit_path is not None:
            raise ValueError("audit_path requires host-managed runtime")
        if adapter is None:
            audit_sink: AuditSink | None = (
                LocalJSONLAuditSink(audit_path) if audit_path is not None else None
            )
            runtime = runtime or build_runtime(
                load_config(config_path),
                audit_sink=audit_sink,
            )
        self.adapter = adapter or adapter_factory(runtime=runtime)
        self.now_factory = now_factory or (lambda: datetime.now(UTC))
        self._pending_approvals: dict[str, _PendingApproval] = {}
        self._approval_states: dict[str, HostApprovalResultStatus] = {}

    @classmethod
    def mock_only(
        cls,
        *,
        audit_path: str | Path | None = None,
    ) -> "MCPHostCompatibilityLayer":
        """Return a host layer using the built-in safe mock-only config."""

        return cls(audit_path=audit_path)

    @classmethod
    def from_config(
        cls,
        config_path: str,
        *,
        audit_path: str | Path | None = None,
    ) -> "MCPHostCompatibilityLayer":
        """Return a host layer from an explicit safe config path."""

        return cls(config_path=config_path, audit_path=audit_path)

    def list_tools(self) -> dict[str, Any]:
        """Return JSON-safe host tool descriptors."""

        try:
            tools = [
                HostToolDescriptor(
                    tool_name=_required_adapter_str(tool, "tool_name"),
                    capability=_required_adapter_str(tool, "capability"),
                    description=_required_adapter_str(tool, "description"),
                    dangerous=bool(tool.get("dangerous", False)),
                ).to_dict()
                for tool in self.adapter.list_tools()
            ]
        except Exception as exc:  # pragma: no cover - covered through behavior
            return self.serialize_error(exc)
        return _json_safe({"status": HostResultStatus.OK.value, "tools": tools})

    def get_tool_schema(self, tool_name: str) -> dict[str, Any]:
        """Return a JSON-safe schema for one tool."""

        if not tool_name:
            return HostError(
                status=HostResultStatus.VALIDATION_ERROR,
                reason="host tool_name is required",
            ).to_dict()
        payload = self.adapter.tool_schema(tool_name)
        if payload.get("status") != HostResultStatus.OK.value:
            return HostError(
                status=HostResultStatus.VALIDATION_ERROR,
                reason=str(payload.get("reason", "tool schema unavailable")),
                tool_name=tool_name,
                details={"adapter_status": payload.get("status")},
            ).to_dict()
        try:
            return HostToolSchema.from_adapter_schema(payload).to_dict()
        except Exception as exc:  # pragma: no cover - defensive
            return self.serialize_error(exc, tool_name=tool_name)

    def tool_schema(self, tool_name: str) -> dict[str, Any]:
        """Alias for compatibility with adapter-style callers."""

        return self.get_tool_schema(tool_name)

    def call_tool(self, request: HostToolCall | Mapping[str, Any]) -> dict[str, Any]:
        """Route a host-style tool call through the SDK adapter."""

        try:
            host_call = (
                request if isinstance(request, HostToolCall) else HostToolCall.from_mapping(request)
            )
            adapter_result = self.adapter.call_tool(
                MCPSDKToolCall(
                    tool_name=host_call.tool_name,
                    target=host_call.target,
                    session_id=host_call.session_id,
                    requester_id=host_call.requester_id,
                    params=host_call.params,
                    provider=host_call.provider,
                    requested_mode=host_call.requested_mode,
                    policy_ref=host_call.policy_ref,
                    approval_context=host_call.approval_context,
                    correlation_id=host_call.correlation_id,
                )
            )
            result_payload = HostToolResult.from_adapter_result(adapter_result).to_dict()
            if result_payload["status"] == HostResultStatus.APPROVAL_REQUIRED.value:
                approval = HostApprovalRequest.from_host_result(
                    result_payload,
                    params=host_call.params,
                    correlation_id=host_call.correlation_id,
                )
                self._pending_approvals[approval.id] = _PendingApproval(
                    call=host_call,
                    approval=approval,
                )
                result_payload["approval_request"] = approval.to_dict()
            return result_payload
        except Exception as exc:
            tool_name = request.tool_name if isinstance(request, HostToolCall) else None
            if isinstance(request, Mapping) and isinstance(request.get("tool_name"), str):
                tool_name = request["tool_name"]
            return self.serialize_error(exc, tool_name=tool_name)

    def submit_approval_response(
        self,
        response: HostApprovalResponse | Mapping[str, Any],
    ) -> dict[str, Any]:
        """Submit an explicit host approval response without executing it."""

        try:
            host_response = (
                response
                if isinstance(response, HostApprovalResponse)
                else HostApprovalResponse.from_mapping(response)
            )
            pending = self._pending_approvals.get(host_response.request_id)
            if pending is None:
                return self._approval_validation_error(
                    request_id=host_response.request_id,
                    reason="unknown approval request",
                    response=host_response,
                )
            mismatch = _approval_mismatch(pending.approval, host_response)
            if mismatch is not None:
                return self._approval_validation_error(
                    request_id=host_response.request_id,
                    reason=mismatch,
                    approval=pending.approval,
                    response=host_response,
                )
            if (
                host_response.decision == HostApprovalDecision.EXPIRED
                or host_response.decided_at >= pending.approval.expires_at
            ):
                self._approval_states[host_response.request_id] = (
                    HostApprovalResultStatus.EXPIRED
                )
                self._emit_approval_event(
                    AuditEventType.APPROVAL_EXPIRED,
                    pending=pending,
                    response=host_response,
                    result_status=HostApprovalResultStatus.EXPIRED,
                )
                return HostApprovalResult(
                    status=HostApprovalResultStatus.EXPIRED,
                    request_id=host_response.request_id,
                    reason="approval expired",
                    approval_request=pending.approval,
                    response=host_response,
                ).to_dict()
            if host_response.decision == HostApprovalDecision.DENIED:
                self._approval_states[host_response.request_id] = (
                    HostApprovalResultStatus.DENIED
                )
                self._emit_approval_event(
                    AuditEventType.APPROVAL_DENIED,
                    pending=pending,
                    response=host_response,
                    result_status=HostApprovalResultStatus.DENIED,
                )
                return HostApprovalResult(
                    status=HostApprovalResultStatus.DENIED,
                    request_id=host_response.request_id,
                    reason="approval denied",
                    approval_request=pending.approval,
                    response=host_response,
                ).to_dict()

            grant = ApprovalGrant(
                request_id=pending.approval.id,
                response_id=f"host-response-{pending.approval.id}-{host_response.operator_id}",
                capability_id=pending.approval.capability,
                session_id=pending.approval.session_id,
                target_id=pending.approval.target,
                provider_id=pending.approval.provider,
                params_fingerprint=pending.approval.params_fingerprint,
                expires_at=pending.approval.expires_at,
                scope=ApprovalGrantScope(host_response.scope.value),
                operator=Actor(type=ActorType.OPERATOR, id=host_response.operator_id),
            )
            self._approval_store().add_action_grant(grant)
            self._approval_states[host_response.request_id] = HostApprovalResultStatus.GRANTED
            self._emit_approval_event(
                AuditEventType.APPROVAL_GRANTED,
                pending=pending,
                response=host_response,
                result_status=HostApprovalResultStatus.GRANTED,
            )
            return HostApprovalResult(
                status=HostApprovalResultStatus.GRANTED,
                request_id=host_response.request_id,
                reason="approval granted",
                approval_request=pending.approval,
                response=host_response,
                grant=grant.to_dict(),
            ).to_dict()
        except Exception as exc:
            request_id = (
                response.request_id if isinstance(response, HostApprovalResponse) else ""
            )
            if isinstance(response, Mapping) and isinstance(response.get("request_id"), str):
                request_id = response["request_id"]
            return HostApprovalResult(
                status=HostApprovalResultStatus.VALIDATION_ERROR,
                request_id=request_id,
                reason=str(exc),
            ).to_dict()

    def resume_approved_tool(self, approval_request_id: str) -> dict[str, Any]:
        """Resume a pending host tool call after an explicit approval grant."""

        pending = self._pending_approvals.get(approval_request_id)
        if pending is None:
            return HostError(
                status=HostResultStatus.VALIDATION_ERROR,
                reason="unknown approval request",
            ).to_dict()
        state = self._approval_states.get(approval_request_id)
        if state in {
            HostApprovalResultStatus.DENIED,
            HostApprovalResultStatus.EXPIRED,
            HostApprovalResultStatus.VALIDATION_ERROR,
        }:
            return HostError(
                status=HostResultStatus.VALIDATION_ERROR,
                reason=state.value,
            ).to_dict()
        return self.call_tool(pending.call)

    def serialize_result(self, result: HostToolResult | Mapping[str, Any]) -> dict[str, Any]:
        """Return a JSON-safe host result payload."""

        if isinstance(result, HostToolResult):
            return result.to_dict()
        return HostToolResult.from_adapter_result(result).to_dict()

    def serialize_error(
        self,
        exc: Exception,
        *,
        status: HostResultStatus = HostResultStatus.VALIDATION_ERROR,
        tool_name: str | None = None,
    ) -> dict[str, Any]:
        """Return a JSON-safe host error payload."""

        return HostError.from_exception(exc, status=status, tool_name=tool_name).to_dict()

    def _approval_store(self) -> ApprovalStore:
        runtime = getattr(self.adapter, "runtime", None)
        store = getattr(runtime, "approval_store", None)
        if not isinstance(store, ApprovalStore):
            raise ValueError("host approval store is unavailable")
        return store

    def _approval_validation_error(
        self,
        *,
        request_id: str,
        reason: str,
        approval: HostApprovalRequest | None = None,
        response: HostApprovalResponse | None = None,
    ) -> dict[str, Any]:
        if approval is not None and response is not None:
            pending = self._pending_approvals.get(approval.id)
            if pending is not None:
                self._emit_approval_event(
                    AuditEventType.APPROVAL_DENIED,
                    pending=pending,
                    response=response,
                    result_status=HostApprovalResultStatus.VALIDATION_ERROR,
                )
        self._approval_states[request_id] = HostApprovalResultStatus.VALIDATION_ERROR
        return HostApprovalResult(
            status=HostApprovalResultStatus.VALIDATION_ERROR,
            request_id=request_id,
            reason=reason,
            approval_request=approval,
            response=response,
        ).to_dict()

    def _emit_approval_event(
        self,
        event_type: AuditEventType,
        *,
        pending: _PendingApproval,
        response: HostApprovalResponse,
        result_status: HostApprovalResultStatus,
    ) -> None:
        capability = DEFAULT_CAPABILITY_REGISTRY.require(pending.approval.capability)
        event = build_audit_event(
            event_type=event_type,
            correlation_id=pending.call.correlation_id
            or f"host-approval:{pending.approval.id}",
            session_id=pending.approval.session_id,
            target_id=pending.approval.target,
            actor=Actor(type=ActorType.OPERATOR, id=response.operator_id),
            capability=CapabilityRef.from_capability(capability),
            policy_decision=PolicyDecision(pending.approval.policy_decision),
            request={"approval_request": pending.approval.to_dict()},
            result={
                "status": result_status.value,
                "approval_response": response.to_dict(),
            },
            material_risks=pending.approval.material_risks,
        )
        self.adapter.runtime.audit_sink.emit(event)


def _required_adapter_str(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"adapter tool metadata missing {key}")
    return value


def _json_safe(value: Any) -> Any:
    """Return a JSON-compatible copy of a value."""

    return json.loads(json.dumps(value, sort_keys=True))


def _approval_mismatch(
    approval: HostApprovalRequest,
    response: HostApprovalResponse,
) -> str | None:
    checks = (
        ("session_id", response.session_id, approval.session_id),
        ("target", response.target, approval.target),
        ("provider", response.provider, approval.provider),
        ("capability", response.capability, approval.capability),
        ("params_fingerprint", response.params_fingerprint, approval.params_fingerprint),
    )
    for label, actual, expected in checks:
        if actual is not None and actual != expected:
            return f"approval {label} mismatch"
    return None


__all__ = ["MCPHostCompatibilityLayer"]
