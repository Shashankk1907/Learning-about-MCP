import logging
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.config.settings import Settings
from mcp_server.security.audit import AuditLogger
from mcp_server.security.auth import AuthProvider, Identity
from mcp_server.security.interceptor import SecurityInterceptor
from mcp_server.security.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class SecureMCP:
    """Wrapper around FastMCP that enforces security across the full protocol surface."""

    def __init__(
        self,
        name: str,
        settings: Settings,
        auth_provider: AuthProvider,
        audit_logger: AuditLogger,
        rate_limiter: RateLimiter,
    ):
        self.settings = settings
        self.auth = auth_provider
        self.audit = audit_logger
        self.rate_limiter = rate_limiter

        # Initialize standard FastMCP with configured host and port
        self._mcp = FastMCP(
            name,
            host=self.settings.server.host,
            port=self.settings.server.port,
        )

        # Initialize security interceptor
        self._interceptor = SecurityInterceptor(
            auth_provider=self.auth,
            audit_logger=self.audit,
            rate_limiter=self.rate_limiter,
            security_config=self.settings.security
        )

        # Registry for fine-grained scopes
        self._tool_scopes: dict[str, list[str]] = {}
        self._resource_scopes: dict[str, list[str]] = {}

    async def call_tool_secure(self, name: str, arguments: dict[str, Any], identity: Identity):
        """Execute a tool with explicit authorization check for a specific identity."""
        from mcp_server.security.auth import authorize

        # Determine required scopes
        scopes = self._tool_scopes.get(name)
        if not scopes:
            # Fallback to the same default logic as the interceptor
            scopes = ["tools:execute"]

        # Enforce authorization
        authorize(identity, scopes)

        # Execute the tool
        return await self._mcp.call_tool(name, arguments)

    def tool(self, name: str | None = None, description: str | None = None, required_scopes: list[str] | None = None):
        """Decorator to register a secure tool."""
        def decorator(func: Callable):
            tool_name = name or func.__name__
            if required_scopes:
                self._tool_scopes[tool_name] = required_scopes

            # Security is enforced at the protocol level by the SecurityInterceptor.
            return self._mcp.tool(name=tool_name, description=description)(func)

        return decorator

    def resource(self, uri: str, name: str | None = None, description: str | None = None, mime_type: str | None = None, required_scopes: list[str] | None = None):
        """Decorator to register a secure resource."""
        def decorator(func: Callable):
            if required_scopes:
                self._resource_scopes[uri] = required_scopes

            return self._mcp.resource(uri, name=name, description=description, mime_type=mime_type)(func)

        return decorator

    def run(self, transport: str = "stdio"):
        """Apply security interceptor and run the underlying FastMCP server."""

        # Apply the interceptor to the low-level server handlers just before running.
        # This ensures all handlers (including discovery) are wrapped.
        self._interceptor.apply(self._mcp._mcp_server)

        # Inject tool/resource scopes into the interceptor so it can enforce them
        self._interceptor._tool_scopes = self._tool_scopes
        self._interceptor._resource_scopes = self._resource_scopes

        logger.info("Starting SecureMCP with transport=%s", transport)
        if transport == "stdio":
            self._mcp.run(transport="stdio")
        elif transport == "sse":
            self._mcp.run(transport="sse")
        else:
            raise ValueError(f"Unsupported transport: {transport}")

