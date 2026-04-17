import os
from unittest.mock import MagicMock, patch

import pytest
from mcp import types
from mcp.server.lowlevel.server import RequestContext, request_ctx

from mcp_server.config.settings import Settings
from mcp_server.core.app import SecureMCP
from mcp_server.security.audit import AuditLogger
from mcp_server.security.auth import AuthenticationError, AuthorizationError, StdioAuthProvider
from mcp_server.security.rate_limiter import RateLimiter, RateLimitExceeded


@pytest.fixture
def settings():
    # Use a fixed key for tests
    s = Settings()
    s.security.auth_key = "test-secret"
    s.security.default_roles = ["test_role"]
    s.security.default_scopes = ["basic"]
    s.security.rate_limit = 100
    s.security.enable_audit_log = False
    return s


@pytest.fixture
def auth_provider(settings):
    return StdioAuthProvider(settings)


@pytest.fixture
def audit_logger(settings):
    return AuditLogger(settings.security)


@pytest.fixture
def rate_limiter(settings):
    return RateLimiter(settings.security.rate_limit)


@pytest.fixture
def app(settings, auth_provider, audit_logger, rate_limiter):
    secure_app = SecureMCP(
        name="TestApp",
        settings=settings,
        auth_provider=auth_provider,
        audit_logger=audit_logger,
        rate_limiter=rate_limiter,
    )
    # Apply interceptor manually for tests
    secure_app._interceptor.apply(secure_app._mcp._mcp_server)
    secure_app._interceptor._tool_scopes = secure_app._tool_scopes
    return secure_app


def mock_request_context(session=None):
    """Utility to set up a mock request context."""
    return RequestContext(
        request_id=1,
        meta=None,
        session=session or MagicMock(),
        lifespan_context=None,
    )


@patch.dict(os.environ, {"MCP_CLIENT_KEY": "test-secret"})
@pytest.mark.asyncio
async def test_successful_tool_call(app):
    @app.tool(name="test_tool", required_scopes=["basic"])
    def test_tool(x: int) -> int:
        return x * 2

    handler = app._mcp._mcp_server.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        params=types.CallToolRequestParams(name="test_tool", arguments={"x": 21})
    )

    token = request_ctx.set(mock_request_context())
    try:
        result = await handler(request)
        # FastMCP wraps the result in a ServerResult(root=CallToolResult(...))
        assert "42" in result.root.content[0].text
    finally:
        request_ctx.reset(token)



@patch.dict(os.environ, {"MCP_CLIENT_KEY": "wrong-secret"})
@pytest.mark.asyncio
async def test_authentication_failure(app):
    handler = app._mcp._mcp_server.request_handlers[types.ListToolsRequest]
    request = types.ListToolsRequest()

    token = request_ctx.set(mock_request_context())
    try:
        with pytest.raises(AuthenticationError):
            await handler(request)
    finally:
        request_ctx.reset(token)


@patch.dict(os.environ, {"MCP_CLIENT_KEY": "test-secret"})
@pytest.mark.asyncio
async def test_authorization_failure(app):
    @app.tool(name="admin_tool", required_scopes=["admin"])
    def admin_tool() -> str:
        return "top secret"

    handler = app._mcp._mcp_server.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        params=types.CallToolRequestParams(name="admin_tool")
    )

    token = request_ctx.set(mock_request_context())
    try:
        with pytest.raises(AuthorizationError):
            await handler(request)
    finally:
        request_ctx.reset(token)


@patch.dict(os.environ, {"MCP_CLIENT_KEY": "test-secret"})
@pytest.mark.asyncio
async def test_base_auth_required_for_discovery(app):
    # Even if no specific scopes are required, authentication is needed for discovery
    handler = app._mcp._mcp_server.request_handlers[types.ListToolsRequest]
    request = types.ListToolsRequest()

    # Wrong key
    with patch.dict(os.environ, {"MCP_CLIENT_KEY": "wrong"}):
        token = request_ctx.set(mock_request_context())
        try:
            with pytest.raises(AuthenticationError):
                await handler(request)
        finally:
            request_ctx.reset(token)


@patch.dict(os.environ, {"MCP_CLIENT_KEY": "test-secret"})
@pytest.mark.asyncio
async def test_rate_limiting(app):
    app._interceptor.rate_limiter = RateLimiter(2)
    handler = app._mcp._mcp_server.request_handlers[types.PingRequest]
    request = types.PingRequest()

    token = request_ctx.set(mock_request_context())
    try:
        # First call - ok
        await handler(request)
        # Second call - ok
        await handler(request)
        # Third call - rate limited
        with pytest.raises(RateLimitExceeded):
            await handler(request)
    finally:
        request_ctx.reset(token)

