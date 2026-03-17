"""Shared MCP server utilities.

Provides common setup patterns used by all Aloha MCP server implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

import structlog

log: structlog.stdlib.BoundLogger = structlog.get_logger().bind(component="mcp_server")

# Type alias for an MCP tool handler.
ToolHandler = Callable[..., Coroutine[Any, Any, Any]]


@dataclass(slots=True)
class ToolDefinition:
    """Describes a single tool that an MCP server exposes."""

    name: str
    description: str
    input_schema: dict[str, Any]
    handler: ToolHandler


@dataclass(slots=True)
class BaseMCPServer:
    """Minimal base for Aloha MCP servers.

    Subclass and register tools via ``register_tool`` before calling ``serve``.
    """

    name: str
    tools: dict[str, ToolDefinition] = field(default_factory=dict)

    def register_tool(self, tool: ToolDefinition) -> None:
        """Add a tool to this server's catalogue."""
        log.info("tool_registered", server=self.name, tool=tool.name)
        self.tools[tool.name] = tool

    async def handle_call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch an incoming tool call to the registered handler.

        Args:
            tool_name: The name of the tool to invoke.
            arguments: The input arguments for the tool.

        Returns:
            Whatever the tool handler returns.

        Raises:
            KeyError: If the tool is not registered.
        """
        defn = self.tools.get(tool_name)
        if defn is None:
            raise KeyError(f"Tool {tool_name!r} not registered on server {self.name!r}")
        log.debug("tool_call", server=self.name, tool=tool_name)
        return await defn.handler(**arguments)

    async def serve(self) -> None:
        """Start serving tool calls.

        Placeholder -- actual transport (stdio / HTTP SSE) will be wired up
        when we integrate with the ``mcp`` SDK.
        """
        log.info("mcp_server_ready", server=self.name, tools=list(self.tools))
