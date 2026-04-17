import pytest

from mcp_server.config.settings import SecurityConfig, ServerConfig, Settings


def test_config_validation():
    # 1. Test SSE transport allowed
    conf = ServerConfig(transport="sse")
    assert conf.transport == "sse"

    # 2. Test invalid transport still fails
    with pytest.raises(ValueError):
        ServerConfig(transport="ftp")

    # 3. Test default scopes (least privilege - empty by default)
    sec = SecurityConfig()
    assert sec.default_scopes == []

def test_settings_load_defaults():
    settings = Settings()
    assert settings.server.transport == "stdio"
    # In LOCAL mode (default), default_scopes should be ["*"]
    assert "*" in settings.security.default_scopes
