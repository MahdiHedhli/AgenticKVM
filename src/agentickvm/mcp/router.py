"""MCP-style router that delegates authority to ControlPlane."""

from __future__ import annotations

from agentickvm.control_plane import (
    ACTClearanceVerifier,
    Actor,
    ActorType,
    ApprovalStore,
    AuthChannel,
    CapabilityRef,
    CapabilityPolicy,
    CapabilityRegistry,
    CapabilityRequest,
    ClearanceClient,
    ControlPlane,
    DEFAULT_AUTH_CHANNEL,
    ControlPlaneResult,
    ControlPlaneStatus,
    DEFAULT_CAPABILITY_REGISTRY,
    InMemoryAuditSink,
    PolicyDecision,
    build_audit_event,
)
from agentickvm.control_plane.audit import AuditEventType, AuditSink
from agentickvm.control_plane.targets import TargetRegistry, TargetRegistryError
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
from agentickvm.providers.registry import ProviderRegistry, ProviderRegistryError


class MCPRouter:
    """Route MCP-style tool requests through the control plane."""

    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        target_registry: TargetRegistry,
        policy: CapabilityPolicy,
        audit_sink: AuditSink | None = None,
        approval_store: ApprovalStore | None = None,
        clearance_client: ClearanceClient | None = None,
        clearance_verifier: ACTClearanceVerifier | None = None,
        clearance_timeout_seconds: int = 20,
        auth_channel: AuthChannel | str = DEFAULT_AUTH_CHANNEL,
        registry: MCPToolRegistry = DEFAULT_MCP_TOOL_REGISTRY,
        capability_registry: CapabilityRegistry = DEFAULT_CAPABILITY_REGISTRY,
        control_plane_factory: type[ControlPlane] = ControlPlane,
    ) -> None:
        self.provider_registry = provider_registry
        self.target_registry = target_registry
        self.policy = policy
        self.audit_sink = audit_sink or InMemoryAuditSink()
        self.approval_store = approval_store
        self.clearance_client = clearance_client
        self.clearance_verifier = clearance_verifier
        self.clearance_timeout_seconds = clearance_timeout_seconds
        self.auth_channel = auth_channel
        self.registry = registry
        self.capability_registry = capability_registry
        self.control_plane_factory = control_plane_factory

    def handle_tool_request(self, request: MCPToolRequest) -> MCPToolResult:
        """Validate, map, and route a tool-style request."""

        tool = self.registry.get(request.tool_name)
        if tool is None:
            self._audit_validation_error(request, "unknown MCP tool")
            return MCPToolResult(
                status=MCPResultStatus.VALIDATION_ERROR,
                tool_name=request.tool_name,
                capability=None,
                target=request.target,
                provider=request.provider or "",
                reason="unknown MCP tool",
            )

        capability = self.capability_registry.get(tool.capability_id)
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
                provider=request.provider or "",
                reason="unknown mapped capability",
            )

        try:
            target = self.target_registry.resolve_enabled(
                request.target,
                mode=self.policy.mode,
            )
        except TargetRegistryError as exc:
            self._audit_validation_error(request, str(exc))
            return MCPToolResult(
                status=MCPResultStatus.VALIDATION_ERROR,
                tool_name=request.tool_name,
                capability=tool.capability_id,
                target=request.target,
                provider=request.provider or "",
                reason=str(exc),
            )

        if request.provider is not None:
            try:
                self.target_registry.validate_provider_match(
                    request.target,
                    request.provider,
                )
            except TargetRegistryError as exc:
                self._audit_validation_error(request, str(exc))
                return MCPToolResult(
                    status=MCPResultStatus.VALIDATION_ERROR,
                    tool_name=request.tool_name,
                    capability=tool.capability_id,
                    target=request.target,
                    provider=request.provider,
                    reason=str(exc),
                )

        try:
            provider = self.provider_registry.resolve_enabled(target.provider_id)
        except ProviderRegistryError as exc:
            self._audit_validation_error(request, str(exc))
            return MCPToolResult(
                status=MCPResultStatus.VALIDATION_ERROR,
                tool_name=request.tool_name,
                capability=tool.capability_id,
                target=request.target,
                provider=target.provider_id,
                reason=str(exc),
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
        control_plane = self.control_plane_factory(
            policy=self.policy,
            provider=provider,
            audit_sink=self.audit_sink,
            registry=self.capability_registry,
            approval_store=self.approval_store,
            clearance_client=self.clearance_client,
            clearance_verifier=self.clearance_verifier,
            clearance_timeout_seconds=self.clearance_timeout_seconds,
            auth_channel=self.auth_channel,
        )
        try:
            result: ControlPlaneResult = control_plane.handle(capability_request)
        except ValueError as exc:
            return MCPToolResult(
                status=MCPResultStatus.POLICY_ERROR,
                tool_name=request.tool_name,
                capability=tool.capability_id,
                target=request.target,
                provider=target.provider_id,
                reason=str(exc),
            )
        except RuntimeError as exc:
            return MCPToolResult(
                status=MCPResultStatus.POLICY_ERROR,
                tool_name=request.tool_name,
                capability=tool.capability_id,
                target=request.target,
                provider=target.provider_id,
                reason=str(exc),
            )

        return mcp_result_from_control_plane(
            request=request,
            capability_id=tool.capability_id,
            provider_id=target.provider_id,
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
        capability = self.capability_registry.require("runtime.noop")
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
        self.audit_sink.emit(event)


def _credential_id_from_request(request: MCPToolRequest) -> str | None:
    value = request.approval_context.get("credential_id")
    if isinstance(value, str) and value:
        return value
    value = request.params.get("credential_id")
    if isinstance(value, str) and value:
        return value
    return None
