"""MCP-facing internal request and response models.

These are MCP-style models, not a live MCP SDK adapter. A future server should
translate SDK calls into these models and route them through `MCPRouter`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping

from agentickvm.control_plane import (
    ControlMode,
    ControlPlaneResult,
    ControlPlaneStatus,
    fingerprint_parameters,
    redact_mapping,
)


class MCPResultStatus(StrEnum):
    """Structured MCP result statuses."""

    OK = "ok"
    DENIED = "denied"
    APPROVAL_REQUIRED = "approval_required"
    CLEARANCE_REQUIRED = "clearance_required"
    VALIDATION_ERROR = "validation_error"
    PROVIDER_ERROR = "provider_error"
    POLICY_ERROR = "policy_error"


@dataclass(frozen=True)
class MCPToolRequest:
    """Tool-style request entering the MCP interface layer."""

    tool_name: str
    target: str
    session_id: str
    requester_id: str
    params: Mapping[str, Any] = field(default_factory=dict)
    provider: str | None = None
    requested_mode: ControlMode | str | None = None
    policy_ref: str | None = None
    approval_context: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        if not self.tool_name:
            raise ValueError("MCP tool name is required")
        if not self.target:
            raise ValueError("MCP target is required")
        if not self.session_id:
            raise ValueError("MCP session_id is required")
        if not self.requester_id:
            raise ValueError("MCP requester_id is required")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        object.__setattr__(
            self,
            "approval_context",
            MappingProxyType(dict(self.approval_context)),
        )


@dataclass(frozen=True)
class MCPToolResult:
    """Sanitized result returned by the MCP router."""

    status: MCPResultStatus
    tool_name: str
    capability: str | None
    target: str
    provider: str
    reason: str
    data: Mapping[str, Any] = field(default_factory=dict)
    approval_request_id: str | None = None
    risks: tuple[str, ...] = ()
    redactions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", MappingProxyType(dict(self.data)))

    def to_dict(self) -> dict[str, Any]:
        """Return a stable, MCP-safe dictionary."""

        payload: dict[str, Any] = {
            "status": self.status.value,
            "tool_name": self.tool_name,
            "capability": self.capability,
            "target": self.target,
            "provider": self.provider,
            "reason": self.reason,
            "data": dict(self.data),
            "risks": list(self.risks),
            "redactions": list(self.redactions),
        }
        if self.approval_request_id is not None:
            payload["approval_request_id"] = self.approval_request_id
        return payload


def mcp_result_from_control_plane(
    *,
    request: MCPToolRequest,
    capability_id: str,
    provider_id: str,
    result: ControlPlaneResult,
) -> MCPToolResult:
    """Translate a control-plane result into an MCP-safe result."""

    if result.status == ControlPlaneStatus.DENIED:
        return MCPToolResult(
            status=MCPResultStatus.DENIED,
            tool_name=request.tool_name,
            capability=capability_id,
            target=request.target,
            provider=provider_id,
            reason=result.decision.reason,
            risks=result.decision.material_risks,
        )

    if result.status in {
        ControlPlaneStatus.APPROVAL_REQUIRED,
        ControlPlaneStatus.CLEARANCE_REQUIRED,
    }:
        if result.status == ControlPlaneStatus.CLEARANCE_REQUIRED:
            clearance = result.clearance_request
            preview, redactions = redact_mapping(request.params)
            return MCPToolResult(
                status=MCPResultStatus.CLEARANCE_REQUIRED,
                tool_name=request.tool_name,
                capability=capability_id,
                target=request.target,
                provider=provider_id,
                reason=result.message,
                data={
                    "clearance_request": clearance.to_dict() if clearance is not None else {},
                    "params_preview": dict(preview),
                    "params_fingerprint": fingerprint_parameters(request.params),
                    "policy_decision": result.decision.decision.value,
                    "retry_guidance": (
                        "Surface this code to the operator and retry with "
                        "identical parameters after approval."
                    ),
                },
                approval_request_id=clearance.request_id if clearance is not None else None,
                risks=result.decision.material_risks,
                redactions=tuple(f"params.{path}" for path in redactions),
            )
        approval = result.approval_request
        preview, redactions = redact_mapping(request.params)
        return MCPToolResult(
            status=MCPResultStatus.APPROVAL_REQUIRED,
            tool_name=request.tool_name,
            capability=capability_id,
            target=request.target,
            provider=provider_id,
            reason=result.message,
            data={
                "approval_request": approval.to_dict() if approval is not None else {},
                "params_preview": dict(preview),
                "params_fingerprint": fingerprint_parameters(request.params),
                "policy_decision": result.decision.decision.value,
            },
            approval_request_id=approval.id if approval is not None else None,
            risks=result.decision.material_risks,
            redactions=tuple(f"params.{path}" for path in redactions),
        )

    if result.status == ControlPlaneStatus.FAILED:
        provider_result = result.provider_result
        data = {"provider_result": provider_result.normalized() if provider_result else {}}
        safe_data, redactions = redact_mapping(data)
        return MCPToolResult(
            status=MCPResultStatus.PROVIDER_ERROR,
            tool_name=request.tool_name,
            capability=capability_id,
            target=request.target,
            provider=provider_id,
            reason=result.message,
            data=dict(safe_data),
            risks=result.decision.material_risks,
            redactions=tuple(f"data.{path}" for path in redactions),
        )

    provider_result = result.provider_result
    data = {"provider_result": provider_result.normalized() if provider_result else {}}
    safe_data, redactions = redact_mapping(data)
    return MCPToolResult(
        status=MCPResultStatus.OK,
        tool_name=request.tool_name,
        capability=capability_id,
        target=request.target,
        provider=provider_id,
        reason=result.message,
        data=dict(safe_data),
        risks=result.decision.material_risks,
        redactions=tuple(f"data.{path}" for path in redactions),
    )
