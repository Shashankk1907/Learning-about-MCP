"""Configuration settings — Pydantic v2 + YAML file support.

Precedence (highest → lowest):
    1. Environment variables  (MCP_LLM__DEFAULT_MODEL=my-model)
    2. config.yaml values
    3. Built-in defaults

The correct precedence is enforced via pydantic-settings' custom sources:
env vars are placed in the source chain *before* YAML, so they always win.
"""
from __future__ import annotations

import logging
import os
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config.yaml"


# ---------------------------------------------------------------------------
# Models and Enums
# ---------------------------------------------------------------------------

class AppMode(StrEnum):
    DEV = "dev"
    LOCAL = "local"
    PROD = "prod"


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8080
    transport: str = "stdio"
    production: bool = False
    mode: AppMode = AppMode.LOCAL

    @field_validator("transport")
    @classmethod
    def _validate_transport(cls, v: str) -> str:
        allowed = {"stdio", "sse"}
        if v not in allowed:
            raise ValueError(f"transport must be one of {allowed}, got {v!r}")
        return v


class SecurityConfig(BaseModel):
    # If production is True, at least one key must be provided.
    auth_keys: list[str] = []
    rate_limit: int = 60           # max requests/minute per identity
    enable_audit_log: bool = True

    # Request protections
    max_request_size: int = 1048576  # 1MB
    request_timeout: float = 30.0    # 30 seconds

    # Authenticated users get these scopes by default.
    # Least privilege: Empty by default.
    default_scopes: list[str] = []
    default_roles: list[str] = ["user"]

    @property
    def auth_key(self) -> str | None:
        return self.auth_keys[0] if self.auth_keys else None

    @auth_key.setter
    def auth_key(self, value: str | None) -> None:
        if value is None:
            self.auth_keys = []
        else:
            self.auth_keys = [value]


class LLMConfig(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    default_model: str = "llama3.2"
    timeout: float = 60.0          # seconds per Ollama request
    max_concurrency: int = 2       # max simultaneous requests to LLM


# ---------------------------------------------------------------------------
# YAML settings source
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
        logger.debug("Loaded config from %s", path)
        return data
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.warning("Could not read config file %s: %s", path, exc)
        return {}


class _YamlSource(PydanticBaseSettingsSource):
    """Custom pydantic-settings source that reads from a YAML file.

    Sits *below* EnvSettingsSource in the priority chain so env vars always win.
    """

    def __init__(self, settings_cls: type[BaseSettings], path: Path) -> None:
        super().__init__(settings_cls)
        self._data = _load_yaml(path)

    def get_field_value(
        self, field: Any, field_name: str
    ) -> tuple[Any, str, bool]:
        val = self._data.get(field_name)
        return val, field_name, self.field_is_complex(field)

    def field_is_complex(self, field: Any) -> bool:  # type: ignore[override]
        return True

    def __call__(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field_name in self.settings_cls.model_fields:
            val = self._data.get(field_name)
            if val is not None:
                result[field_name] = val
        return result


# ---------------------------------------------------------------------------
# Top-level Settings
# ---------------------------------------------------------------------------

# Class-level mutable slot so load() can inject the YAML path before __init__.
_yaml_path_slot: Path = _DEFAULT_CONFIG_PATH


class Settings(BaseSettings):
    """Top-level settings.

    Always use Settings.load() (not Settings()) so that the YAML path
    is correctly injected before the source chain runs.
    """

    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_prefix="MCP_",
        extra="ignore",
    )

    server: ServerConfig = ServerConfig()
    security: SecurityConfig = SecurityConfig()
    llm: LLMConfig = LLMConfig()

    @field_validator("security")
    @classmethod
    def _validate_security(cls, v: SecurityConfig, info: Any) -> SecurityConfig:
        return v

    def model_post_init(self, __context: Any) -> None:
        """Apply profile-specific overrides based on server.mode."""
        mode = self.server.mode

        if mode == AppMode.PROD:
            # Enforce strict production settings
            self.server.production = True
            self.security.enable_audit_log = True
            # Minimal defaults for production
            if not self.security.auth_keys:
                 raise ValueError(
                    "In PROD mode, at least one security.auth_keys must be configured."
                )
        elif mode == AppMode.LOCAL:
            # Convenience defaults for local use
            self.server.production = False
            # Local mode gets broad default permissions for ease of use
            if not self.security.default_scopes and "default_scopes" not in self.model_fields_set:
                self.security.default_scopes = ["*"]
        elif mode == AppMode.DEV:
            self.server.production = False
            self.security.enable_audit_log = False
            if not self.security.default_scopes and "default_scopes" not in self.model_fields_set:
                 self.security.default_scopes = ["*"]

        if self.server.production and not self.security.auth_keys:
            raise ValueError(
                "In PRODUCTION mode, at least one security.auth_keys must be configured. "
                "The server will not start in OPEN mode when production=True."
            )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Priority: env vars > YAML > built-in defaults
        # init_settings intentionally excluded — use Settings.load() factory.
        return (env_settings, _YamlSource(settings_cls, _yaml_path_slot))

    @classmethod
    def load(cls, config_file: Path | None = None) -> Settings:
        """Factory that sets the YAML path before the source chain runs.

        Args:
            config_file: explicit path; falls back to MCP_CONFIG_FILE env var,
                         then to <repo-root>/config.yaml.
        """
        global _yaml_path_slot
        _yaml_path_slot = config_file or Path(
            os.environ.get("MCP_CONFIG_FILE", str(_DEFAULT_CONFIG_PATH))
        )
        return cls()
