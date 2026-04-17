"""Authentication models and providers for MCP.

Providers fetch the identity from context (environment, HTTP headers, etc.).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mcp.server.lowlevel.server import RequestContext

    from mcp_server.config.settings import Settings

logger = logging.getLogger(__name__)


def get_identity_label(
    transport: str,
    provided_key: str | None = None,
    ip: str | None = None,
) -> str:
    """Consistently derive a label for an identity.

    - Authenticated: bucket by key fingerprint
    - Unauthenticated HTTP/SSE: bucket by client IP
    - Unknown/unavailable IP: bucket by a conservative shared fallback label
    """
    if provided_key:
        # Use first 12 chars of SHA-256 for a stable, non-reversible fingerprint.
        fingerprint = hashlib.sha256(provided_key.encode()).hexdigest()[:12]
        return f"key:{fingerprint}"

    if ip:
        return f"{transport}:{ip}"

    return "anonymous"


@dataclass(frozen=True)
class Identity:
    subject: str
    roles: list[str] = field(default_factory=lambda: ["user"])
    scopes: list[str] = field(default_factory=lambda: [])
    label: str = "anonymous"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        return self.label.startswith("key:")


ANONYMOUS = Identity(subject="anonymous", roles=["user"], scopes=["*"], label="anonymous")


class AuthorizationError(Exception):
    """Raised when an identity lacks required scopes."""
    pass


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


def authorize(identity: Identity, required_scopes: list[str] | None) -> None:
    """Check if identity has the required scopes. Raises AuthorizationError if forbidden."""
    if not required_scopes:
        return
    if "*" in identity.scopes:
        return
    missing = [s for s in required_scopes if s not in identity.scopes]
    if missing:
        raise AuthorizationError(f"Forbidden: missing scopes {missing}")


class AuthProvider(ABC):
    """Abstract base class for providing an identity for the current request context."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.security = settings.security
        self._default_roles = self.security.default_roles
        self._default_scopes = self.security.default_scopes
        self._production = settings.server.production

        if not self.security.auth_keys:
            if self._production:
                # This should already be caught by Settings validation,
                # but we double-check here as a fail-safe.
                raise AuthenticationError("Production mode requires at least one auth key.")
            logger.warning(
                "Authentication keys are not set — running in OPEN mode."
            )

    @property
    def open_mode(self) -> bool:
        return not self.security.auth_keys

    def _verify_key(self, provided_key: str | None) -> None:
        """Verify the provided key against allowed keys using constant-time comparison."""
        if self.open_mode:
            return

        if not provided_key:
            raise AuthenticationError("Authentication required.")

        # Constant-time check against all allowed keys
        is_valid = any(
            hmac.compare_digest(provided_key, allowed_key)
            for allowed_key in self.security.auth_keys
        )

        if not is_valid:
            raise AuthenticationError("Authentication failed: invalid key.")

    @abstractmethod
    def get_identity(self, context: RequestContext) -> Identity:
        """Resolve the identity of the current caller from the request context."""
        pass


class StdioAuthProvider(AuthProvider):
    """Retrieves credentials from the process environment, suitable for stdio transport."""

    def get_identity(self, context: RequestContext) -> Identity:
        provided_key = os.environ.get("MCP_CLIENT_KEY")

        if self.open_mode:
            label = get_identity_label("stdio")
            return Identity(subject="anonymous", roles=["user"], scopes=["*"], label=label)

        self._verify_key(provided_key)
        label = get_identity_label("stdio", provided_key=provided_key)

        return Identity(
            subject="client",
            roles=self._default_roles,
            scopes=self._default_scopes,
            label=label,
        )


class HttpAuthProvider(AuthProvider):
    """Retrieves credentials from HTTP headers, suitable for SSE/HTTP transport."""

    def get_identity(self, context: RequestContext) -> Identity:
        request = getattr(context, "request", None)
        if request is None:
            raise AuthenticationError("Transport request context not available.")

        # Best-effort client IP detection
        client_ip = None
        if hasattr(request, "client") and request.client:
            client_ip = request.client.host

        # Try X-MCP-Client-Key or Authorization: Bearer <key>
        provided_key = request.headers.get("X-MCP-Client-Key")
        if not provided_key:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                provided_key = auth_header[len("Bearer "):]

        if self.open_mode:
            label = get_identity_label("http", ip=client_ip)
            return Identity(subject="anonymous", roles=["user"], scopes=["*"], label=label)

        self._verify_key(provided_key)
        label = get_identity_label("http", provided_key=provided_key)

        return Identity(
            subject="client",
            roles=self._default_roles,
            scopes=self._default_scopes,
            label=label,
        )

