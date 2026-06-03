"""MCP-style router that delegates authority to ControlPlane."""

from __future__ import annotations

from agentickvm.control_plane import (
    Actor,
    ActorType,
    CapabilityRef,
    CapabilityRequest,
    ControlPlane,
    ControlPlaneResult,
    ControlPlaneStatus,
    PolicyDecision,
    build_audit_event,
)
from agentickvm.control_plane.audit import AuditEventType
from agentickvm.mcp.models import (
    MCPResultStatus,
    MCPToolRequest,
    MCPToolResult,
    mcp_result_from_control_plane,
)
from agentickvm.mcp.registry import (
    DEFAULT_MCP_TOOL_REGISTRY,
    MCPToolRegistry,
)


class MCPRouter:
    """Route MCP-style tool requests through the control plane."""

    def __init__(
        self,
        *,
        control_plane: ControlPlane,
        registry: MCPToolRegistry = DEFAULT_MCP_TOOL_REGISTRY,
    ) -> None:
        self.control_plane = control_plane
        self.registry = registry

    def handle_tool_request(self, request: MCPToolRequest) -> MCPToolResult:
        """Validate, map, and route a tool-style request."""

        if request.provider != self.control_plane.provider.provider_id:
            self._audit_validation_error(request, "unknown MCP provider")
            return MCPToolResult(
                status=MCPResultStatus.VALIDATION_ERROR,
                tool_name=request.tool_name,
                capability=None,
                target=request.target,
                provider=request.provider,
                reason="unknown MCP provider",
            )

        tool = self.registry.get(request.tool_name)
        if tool is None:
            self._audit_validation_error(request, "unknown MCP tool")
            return MCPToolResult(
                status=MCPResultStatus.VALIDATION_ERROR,
                tool_name=request.tool_name,
                capability=None,
                target=request.target,
                provider=request.provider,
                reason="unknown MCP tool",
            )

        capability = self.control_plane.registry.get(tool.capability_id)
        if capability is None:
            self._audit_validation_error(
                request,
                f"unknown mapped capability: {tool.capability_id}",
            )
            return MCPToolResult(
                status=MCPResultStatus.POLICY_ERROR,
                tool_name=request.tool_name,
                capability=tool.capability_id,
                target=request.target,
                provider=request.provider,
                reason="unknown mapped capability",
            )

        capability_request = CapabilityRequest(
            capability_id=tool.capability_id,
            target_id=request.target,
            session_id=request.session_id,
            correlation_id=request.correlation_id or f"mcp:{request.tool_name}",
            requester=Actor(type=ActorType.AGENT, id=request.requester_id),
            intended_effect=f"MCP tool {request.tool_name}: {tool.description}",
            parameters=request.params,
            credential_id=_credential_id_from_request(request),
        )
        try:
            result: ControlPlaneResult = self.control_plane.handle(capability_request)
        except ValueError as exc:
            return MCPToolResult(
                status=MCPResultStatus.POLICY_ERROR,
                tool_name=request.tool_name,
                capability=tool.capability_id,
                target=request.target,
                provider=request.provider,
                reason=str(exc),
            )
        except RuntimeError as exc:
            return MCPToolResult(
                status=MCPResultStatus.POLICY_ERROR,
                tool_name=request.tool_name,
                capability=tool.capability_id,
                target=request.target,
                provider=request.provider,
                reason=str(exc),
            )

        return mcp_result_from_control_plane(
            request=request,
            capability_id=tool.capability_id,
            result=result,
        )

    def _audit_validation_error(self, request: MCPToolRequest, reason: str) -> None:
        """Emit a validation result event when the router fails before mapping."""

        # Unknown tool names do not have a valid capability reference, so this
        # router records a result-shaped event through the existing audit sink
        # using a known safe runtime capability.
        capability_request = CapabilityRequest(
            capability_id="runtime.noop",
            target_id=request.target,
            session_id=request.session_id,
            correlation_id=request.correlation_id or f"mcp:{request.tool_name}",
            requester=Actor(type=ActorType.AGENT, id=request.requester_id),
            intended_effect=f"MCP validation error: {reason}",
            parameters=request.params,
        )
        capability = self.control_plane.registry.require("runtime.noop")
        capability_ref = CapabilityRef.from_capability(capability)
        event = build_audit_event(
            event_type=AuditEventType.RESULT_RETURNED,
            correlation_id=capability_request.correlation_id,
            session_id=capability_request.session_id,
            target_id=capability_request.target_id,
            actor=capability_request.requester,
            capability=capability_ref,
            policy_decision=PolicyDecision.DENY,
            request={"tool_name": request.tool_name, "params": dict(request.params)},
            result={"status": ControlPlaneStatus.DENIED.value, "reason": reason},
        )
        self.control_plane.audit_sink.emit(event)


def _credential_id_from_request(request: MCPToolRequest) -> str | None:
    value = request.approval_context.get("credential_id")
    if isinstance(value, str) and value:
        return value
    value = request.params.get("credential_id")
    if isinstance(value, str) and value:
        return value
    return None
