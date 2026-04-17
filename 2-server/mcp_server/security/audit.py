"""Structured audit logging to stderr."""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from mcp_server.config.settings import SecurityConfig
from mcp_server.security.auth import Identity

# Dedicated logger — handlers are attached by main.py, not here.
logger = logging.getLogger("mcp.audit")


class AuditLogger:
    def __init__(self, settings: SecurityConfig) -> None:
        self.enabled = settings.enable_audit_log

    def log_invocation(
        self,
        method: str,
        identity: Identity | None,
        status: str,
        params_keys: list[str] | None = None,
    ) -> None:
        if not self.enabled:
            return

        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "method": method,
            "identity_label": identity.label if identity else "unknown",
            "identity_subject": identity.subject if identity else "unknown",
            "status": status,
            "params_keys": params_keys or [],
        }
        logger.info(json.dumps(entry))
