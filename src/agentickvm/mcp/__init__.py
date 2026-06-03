"""MCP-facing models, registry, and router.

This package intentionally does not start a live MCP server yet. It provides the
safe internal interface that a future SDK adapter must use.
"""

from agentickvm.mcp.models import MCPResultStatus, MCPToolRequest, MCPToolResult
from agentickvm.mcp.registry import (
    DEFAULT_MCP_TOOL_REGISTRY,
    DEFAULT_MCP_TOOLS,
    MCPToolDefinition,
    MCPToolRegistry,
)
from agentickvm.mcp.router import MCPRouter

__all__ = [
    "DEFAULT_MCP_TOOL_REGISTRY",
    "DEFAULT_MCP_TOOLS",
    "MCPResultStatus",
    "MCPRouter",
    "MCPToolDefinition",
    "MCPToolRegistry",
    "MCPToolRequest",
    "MCPToolResult",
]
