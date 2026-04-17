"""Abstract LLM provider interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[dict[str, Any]]] | None = None,
        model: str | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Send a chat request and return the response message dict."""

    @abstractmethod
    async def list_models(self) -> list[str]:
        """Return a list of available model names."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the provider is reachable, False otherwise."""
