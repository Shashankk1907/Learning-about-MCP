"""Protocol-level security interceptor for MCP.

Wraps all Server request handlers to enforce Authentication, Authorization,
Rate Limiting, and Audit Logging across the full MCP surface.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from mcp import types
from mcp.server.lowlevel.server import request_ctx

from mcp_server.security.auth import AuthenticationError, authorize

if TYPE_CHECKING:
    from mcp.server.lowlevel.server import Server

    from mcp_server.config.settings import SecurityConfig
    from mcp_server.security.audit import AuditLogger
    from mcp_server.security.auth import AuthProvider, Identity
    from mcp_server.security.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class SecurityInterceptor:
    """Intersects every MCP request to apply security policies."""

    def __init__(
        self,
        auth_provider: AuthProvider,
        audit_logger: AuditLogger,
        rate_limiter: RateLimiter,
        security_config: SecurityConfig,
    ) -> None:
        self.auth = auth_provider
        self.audit = audit_logger
        self.rate_limiter = rate_limiter
        self.security = security_config

    def apply(self, server: Server) -> None:
        """Wrap all current request handlers on the server."""
        for req_type, handler in server.request_handlers.items():
            server.request_handlers[req_type] = self._wrap_handler(req_type, handler)
        logger.info("Security interceptor applied to %d handlers", len(server.request_handlers))

    def _wrap_handler(self, req_type: type[types.ClientRequest], handler: Callable) -> Callable:
        """Create a security wrapper for a specific handler."""

        async def wrapper(request: Any) -> Any:
            # 1. Get current request context (set by Server._handle_request)
            try:
                ctx = request_ctx.get()
            except LookupError:
                logger.error("SecurityInterceptor called outside of request context")
                return await handler(request)

            identity: Identity | None = None
            method_name = req_type.__name__

            try:
                # 2. Authenticate
                identity = self.auth.get_identity(ctx)

                # 3. Rate Limit
                self.rate_limiter.check(identity.label)

                # 4. Authorize
                # Determine required scopes based on request type
                required_scopes = self._get_required_scopes(request)
                authorize(identity, required_scopes)

                # 5. Audit Start
                self.audit.log_invocation(method_name, identity, "STARTED")

                # 6. Request Size Protection
                # Estimate size by serializing to JSON
                try:
                    # mcp types often have model_dump or can be dict-ified
                    req_data = request.model_dump() if hasattr(request, "model_dump") else str(request)
                    size = len(json.dumps(req_data))
                    if size > self.security.max_request_size:
                        raise ValueError(f"Request size {size} exceeds limit of {self.security.max_request_size}")
                except Exception as ex:
                    if isinstance(ex, ValueError):
                        raise ex
                    logger.warning("Could not calculate request size: %s", ex)

                # 7. Execute with Timeout Protection
                try:
                    result = await asyncio.wait_for(
                        handler(request),
                        timeout=self.security.request_timeout
                    )
                except TimeoutError:
                    raise RuntimeError(f"Request timed out after {self.security.request_timeout}s")

                # 8. Audit Success
                self.audit.log_invocation(method_name, identity, "SUCCESS")
                return result

            except Exception as e:
                # Handle security-specific errors for auditing
                from mcp_server.security.auth import AuthorizationError
                from mcp_server.security.rate_limiter import RateLimitExceeded

                status = "ERROR"
                if isinstance(e, AuthenticationError):
                    status = "UNAUTHORIZED"
                elif isinstance(e, AuthorizationError):
                    status = "FORBIDDEN"
                elif isinstance(e, RateLimitExceeded):
                    status = "RATE_LIMITED"

                if identity or not isinstance(e, (AuthenticationError, AuthorizationError, RateLimitExceeded)):
                   self.audit.log_invocation(method_name, identity, status)

                # Re-raise to let the server handle the error response
                raise e

        return wrapper

    def _get_required_scopes(self, request: Any) -> list[str] | None:
        """Determine required scopes based on the request content."""
        # 1. Base Auth check: All MCP requests require a valid identity (empty list of scopes)
        required = []

        # 2. Specific scopes for execution operations
        if isinstance(request, types.CallToolRequest):
            # Check if this specific tool has required scopes
            tool_name = request.params.name
            tool_scopes = getattr(self, "_tool_scopes", {}).get(tool_name)
            if tool_scopes:
                required.extend(tool_scopes)
            else:
                # Default scope for any tool execution if not specified
                required.append("tools:execute")

        elif isinstance(request, types.ReadResourceRequest):
            # Check if this specific resource URI has required scopes
            uri = str(request.params.uri)
            resource_scopes = getattr(self, "_resource_scopes", {}).get(uri)
            if resource_scopes:
                required.extend(resource_scopes)
            else:
                # Default scope for any resource read if not specified
                required.append("resources:read")

        elif isinstance(request, types.GetPromptRequest):
            required.append("prompts:read")

        # Discovery and other lifecycle methods (Initialize, ListTools, etc.)
        # return the base requirement (authentication)
        return required if required else None

