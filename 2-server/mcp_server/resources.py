"""MCP resources for the server."""
from __future__ import annotations

import json

from mcp_server.config.settings import Settings
from mcp_server.core.app import SecureMCP


def register_resources(app: SecureMCP, settings: Settings):
    """Register resources with the SecureMCP application."""

    @app.resource(
        uri="config://server",
        name="Server Configuration",
        description="Read-only view of the server's active configuration",
        mime_type="application/json",
    )
    def server_info() -> str:
        info = {
            "transport": settings.server.transport,
            "production": settings.server.production,
            "llm_provider": settings.llm.provider,
            "llm_base_url": settings.llm.base_url,
            "llm_default_model": settings.llm.default_model,
            "auth_enabled": len(settings.security.auth_keys) > 0,
            "rate_limit_rpm": settings.security.rate_limit,
        }
        return json.dumps(info, indent=2)
