"""Utility tools for the MCP server."""
from __future__ import annotations

from mcp_server.core.app import SecureMCP


def register_util_tools(app: SecureMCP):
    """Register utility tools with the SecureMCP application."""

    @app.tool(
        name="echo",
        description="Echo a message back to the caller",
        required_scopes=["tools:util:echo"]
    )
    def echo(message: str) -> str:
        return f"Echo: {message}"
