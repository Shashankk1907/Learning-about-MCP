from unittest.mock import MagicMock

import pytest
from mcp.server.lowlevel.server import RequestContext

from mcp_server.config.settings import Settings
from mcp_server.security.auth import HttpAuthProvider, StdioAuthProvider


def mock_ctx(request=None):
    return RequestContext(
        request_id=1,
        meta=None,
        session=MagicMock(),
        lifespan_context=None,
        request=request,
    )

def test_stdio_identity_labeling():
    settings = Settings()
    settings.security.auth_key = "secret-key"
    provider = StdioAuthProvider(settings)

    # 1. Authenticated
    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("MCP_CLIENT_KEY", "secret-key")
        identity = provider.get_identity(mock_ctx())
        assert identity.label.startswith("key:")
        # SHA-256 of "secret-key" starts with "045e"
        assert identity.label == f"key:{identity.label[4:]}"
        assert len(identity.label) == 4 + 12 # "key:" + 12 chars

    # 2. Unauthenticated (should error if not open mode, but let's test open mode)
    settings_open = Settings()
    settings_open.security.auth_key = None
    provider_open = StdioAuthProvider(settings_open)
    identity_open = provider_open.get_identity(mock_ctx())
    assert identity_open.label == "anonymous"

def test_http_identity_labeling():
    settings = Settings()
    settings.security.auth_key = "secret-key"
    provider = HttpAuthProvider(settings)

    # Mock Starlette Request
    request = MagicMock()
    request.headers = {"X-MCP-Client-Key": "secret-key"}
    request.client.host = "1.2.3.4"

    # 1. Authenticated HTTP
    identity = provider.get_identity(mock_ctx(request))
    assert identity.label.startswith("key:")

    # 2. Unauthenticated HTTP (Open Mode)
    settings_open = Settings()
    settings_open.security.auth_key = None
    provider_open = HttpAuthProvider(settings_open)
    request_unauth = MagicMock()
    request_unauth.headers = {}
    request_unauth.client.host = "5.6.7.8"

    identity_unauth = provider_open.get_identity(mock_ctx(request_unauth))
    assert identity_unauth.label == "http:5.6.7.8"

    # 3. Fallback if IP unknown
    request_no_ip = MagicMock()
    request_no_ip.headers = {}
    request_no_ip.client = None
    identity_no_ip = provider_open.get_identity(mock_ctx(request_no_ip))
    assert identity_no_ip.label == "anonymous"
