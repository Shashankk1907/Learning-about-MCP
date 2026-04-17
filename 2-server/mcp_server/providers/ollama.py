"""Ollama LLM provider — wraps the Ollama REST API."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from mcp_server.config.settings import LLMConfig
from mcp_server.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Thin async client for the Ollama local API."""

    def __init__(self, settings: LLMConfig) -> None:
        self.base_url = settings.base_url.rstrip("/")
        self.model = settings.default_model
        self.timeout = settings.timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Send a /api/chat request.

        Args:
            messages: List of chat messages.
            tools: Optional tool definitions.
            model: Optional model override (defaults to self.model).
            stream: Whether to stream the response.

        Returns:
            The 'message' dict from Ollama's response.
        """
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        data = await self._post("/api/chat", payload)
        return data.get("message", {})

    async def list_models(self) -> list[str]:
        """Return names of locally available Ollama models."""
        data = await self._get("/api/tags")
        return [m["name"] for m in data.get("models", [])]

    async def health_check(self) -> bool:
        """Ping Ollama; return True if reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}{path}", json=payload)
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is Ollama running? Start it with: ollama serve"
            )
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}"
            )

    async def _get(self, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}{path}")
                resp.raise_for_status()
                return resp.json()
        except httpx.ConnectError:
            raise RuntimeError(
                f"Cannot connect to Ollama at {self.base_url}. "
                "Is Ollama running? Start it with: ollama serve"
            )
