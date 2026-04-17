"""MCP Server entry point — CLI, wiring, built-in tools, and main loop."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from mcp_server.resources import register_resources
from mcp_server.tools.llm import register_llm_tools
from mcp_server.tools.util import register_util_tools
from mcp_server.tools.weather import register_weather_tools
from mcp_server.config.settings import Settings
from mcp_server.core.app import SecureMCP
from mcp_server.providers.manager import get_provider
from mcp_server.security.audit import AuditLogger
from mcp_server.security.auth import HttpAuthProvider, StdioAuthProvider
from mcp_server.security.rate_limiter import RateLimiter

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def _configure_logging(level: str) -> None:
    """Send all logs to STDERR — stdout is reserved for MCP JSON-RPC traffic."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(numeric)
    root.addHandler(handler)


# ---------------------------------------------------------------------------
# CLI & entry point
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mcp-server",
        description="Local FastMCP server with Layered Architecture",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="FILE",
        help="Path to config.yaml (default: ./config.yaml)",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Logging verbosity (default: info)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    _configure_logging(args.log_level)

    logger = logging.getLogger("mcp.main")
    logger.info("Starting MCP server (transport=%s)", args.transport)

    # ---- Config Layer ----------------------------------------------------
    settings = Settings.load(config_file=args.config)

    # ---- LLM Provider Layer (with Concurrency) ---------------------------
    provider = get_provider(settings.llm)

    # ---- Security Layer --------------------------------------------------
    if args.transport == "sse":
        auth_provider = HttpAuthProvider(settings)
    else:
        auth_provider = StdioAuthProvider(settings)

    audit_logger = AuditLogger(settings.security)
    rate_limiter = RateLimiter(settings.security.rate_limit)


    # ---- API Layer (MCP Application) -------------------------------------
    app = SecureMCP(
        name="Layered MCP Server",
        settings=settings,
        auth_provider=auth_provider,
        audit_logger=audit_logger,
        rate_limiter=rate_limiter,
    )

    # Register tools and resources
    register_llm_tools(app, provider)
    register_util_tools(app)
    register_weather_tools(app)
    register_resources(app, settings)

    # ---- Run -------------------------------------------------------------
    app.run(transport=args.transport)


if __name__ == "__main__":
    main()
