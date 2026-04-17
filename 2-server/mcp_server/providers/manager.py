"""LLM Provider Manager — handles registration, instantiation, and concurrency control."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from mcp_server.config.settings import LLMConfig
from mcp_server.providers.base import LLMProvider
from mcp_server.providers.ollama import OllamaProvider

logger = logging.getLogger(__name__)


class ConcurrencyLimitedProvider(LLMProvider):
    """Wrapper that limits the number of concurrent requests to an underlying provider."""

    def __init__(self, provider: LLMProvider, max_concurrency: int) -> None:
        self._provider = provider
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_concurrency = max_concurrency
        logger.info("Initialized concurrency limit: %d simultaneous requests", max_concurrency)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        async with self._semaphore:
            active = self._max_concurrency - self._semaphore._value
            logger.debug("LLM Chat request starting (active: %d/%d)", active, self._max_concurrency)
            return await self._provider.chat(messages, tools, model, stream)

    async def list_models(self) -> list[str]:
        """Metadata calls are also protected for consistency."""
        return await self._provider.list_models()

    async def health_check(self) -> bool:
        return await self._provider.health_check()


def get_provider(config: LLMConfig) -> LLMProvider:
    """Factory to create and wrap the configured LLM provider."""

    if config.provider == "ollama":
        provider = OllamaProvider(config)
    else:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")

    # Wrap with concurrency protection
    if config.max_concurrency > 0:
        return ConcurrencyLimitedProvider(provider, config.max_concurrency)

    return provider
