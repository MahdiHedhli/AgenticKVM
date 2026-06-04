"""Dependency-free mock-only MCP SDK adapter scaffold."""

from agentickvm.mcp_sdk.adapter import MCPSDKAdapter
from agentickvm.mcp_sdk.models import MCPSDKToolCall

__all__ = [
    "MCPSDKAdapter",
    "MCPSDKToolCall",
]
