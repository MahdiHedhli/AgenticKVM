"""Dependency-free mock-only MCP SDK adapter scaffold."""

from agentickvm.mcp_sdk.adapter import MCPSDKAdapter
from agentickvm.mcp_sdk.approval_models import (
    HostApprovalDecision,
    HostApprovalRequest,
    HostApprovalResponse,
    HostApprovalResult,
    HostApprovalResultStatus,
    HostApprovalScope,
    approval_fingerprint,
)
from agentickvm.mcp_sdk.host import MCPHostCompatibilityLayer
from agentickvm.mcp_sdk.host_models import (
    HOST_RESULT_STATUSES,
    HostError,
    HostResultStatus,
    HostToolCall,
    HostToolDescriptor,
    HostToolResult,
    HostToolSchema,
)
from agentickvm.mcp_sdk.models import MCPSDKToolCall
from agentickvm.mcp_sdk.result_validation import (
    HOST_COMPATIBILITY_STATUSES,
    HostResultValidationError,
    validate_host_result,
)

__all__ = [
    "HOST_COMPATIBILITY_STATUSES",
    "HOST_RESULT_STATUSES",
    "HostApprovalDecision",
    "HostApprovalRequest",
    "HostApprovalResponse",
    "HostApprovalResult",
    "HostApprovalResultStatus",
    "HostApprovalScope",
    "MCPHostCompatibilityLayer",
    "MCPSDKAdapter",
    "MCPSDKToolCall",
    "HostError",
    "HostResultStatus",
    "HostToolCall",
    "HostToolDescriptor",
    "HostToolResult",
    "HostToolSchema",
    "HostResultValidationError",
    "approval_fingerprint",
    "validate_host_result",
]
