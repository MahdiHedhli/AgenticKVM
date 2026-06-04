"""Dependency-free mock-only MCP SDK adapter scaffold."""

from agentickvm.mcp_sdk.adapter import MCPSDKAdapter
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

__all__ = [
    "HOST_RESULT_STATUSES",
    "MCPHostCompatibilityLayer",
    "MCPSDKAdapter",
    "MCPSDKToolCall",
    "HostError",
    "HostResultStatus",
    "HostToolCall",
    "HostToolDescriptor",
    "HostToolResult",
    "HostToolSchema",
]
