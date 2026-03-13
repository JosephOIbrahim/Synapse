"""
Synapse MCP Protocol Layer

Streamable HTTP transport for the Model Context Protocol (MCP 2025-06-18).
Thin protocol adapter on top of existing SYNAPSE handlers and safety middleware.
"""

from .protocol import (
    JsonRpcError,
    JsonRpcParseError,
    JsonRpcInvalidRequest,
    JsonRpcMethodNotFound,
    JsonRpcInvalidParams,
)

from .session import MCPSession, MCPSessionManager

try:
    from .server import MCPServer, SSEEventBus
    MCP_SERVER_AVAILABLE = True
except ImportError:
    MCPServer = None  # type: ignore[assignment,misc]
    SSEEventBus = None  # type: ignore[assignment,misc]
    MCP_SERVER_AVAILABLE = False

__all__ = [
    # Protocol
    "JsonRpcError",
    "JsonRpcParseError",
    "JsonRpcInvalidRequest",
    "JsonRpcMethodNotFound",
    "JsonRpcInvalidParams",
    # Session
    "MCPSession",
    "MCPSessionManager",
    # Server
    "MCPServer",
    "SSEEventBus",
    "MCP_SERVER_AVAILABLE",
]
