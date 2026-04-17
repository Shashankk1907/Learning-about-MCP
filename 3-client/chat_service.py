"""Chat service layer — handles context window and business logic for the chat client."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

from credentials import CredentialManager

logger = logging.getLogger(__name__)

MAX_PROMPT_LENGTH = 5000


class ChatService:
    """Service layer to isolate LLM logic from the Streamlit UI.

    Now routes all calls through the MCP security boundary.
    """

    def __init__(self, server_url: str | None = None) -> None:
        self.credentials = CredentialManager()
        # The client will talk to the server's SSE endpoint by default.
        self.server_url = server_url or os.environ.get("MCP_SERVER_URL", "http://127.0.0.1:8080/sse")

    def _get_headers(self) -> dict[str, str]:
        """Prepare headers with authentication if key is available."""
        headers = {}
        # Precedence handled by CredentialManager
        auth_key = self.credentials.get_key()
        if auth_key:
            headers["X-MCP-Client-Key"] = auth_key
            headers["Authorization"] = f"Bearer {auth_key}"
        return headers

    async def list_models(self) -> list[str]:
        """Return names of locally available Ollama models via MCP tool."""
        try:
            async with sse_client(self.server_url, headers=self._get_headers()) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool("ollama-list-models")
                    # Result content is usually a list of Prompt messages
                    if result and result.content:
                        models_json = result.content[0].text
                        return json.loads(models_json)
            return []
        except Exception as exc:
            logger.error("Failed to list models via MCP: %s", exc)
            return []

    def validate_input(self, prompt: str) -> str:
        """Validate and sanitize user input.

        - Enforce length limits.
        - Strip potential control characters.
        """
        text = prompt.strip()
        if len(text) > MAX_PROMPT_LENGTH:
            raise ValueError(f"Prompt exceeds maximum length of {MAX_PROMPT_LENGTH} characters.")
        if not text:
            raise ValueError("Prompt cannot be empty.")

        # Basic sanitization: strip non-printable characters except newlines/tabs
        cleaned = "".join(c for c in text if c.isprintable() or c in "\n\t")
        return cleaned

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
    ) -> str:
        """Send a chat request through the MCP ollama-chat tool.

        Args:
            messages: Full conversation history from the UI.
            model: Optional model to use.

        Returns:
            The assistant's response content.
        """
        # Validate and sanitize the latest message
        if not messages:
            raise ValueError("No messages provided.")

        messages[-1].update({"content": self.validate_input(messages[-1]["content"])})

        # Enforce 10-message context window (most recent 10 messages)
        truncated_history = messages[-10:] if len(messages) > 10 else messages

        # Clean history for provider (ensure only role/content)
        cleaned_history = [{"role": m["role"], "content": m["content"]} for m in truncated_history]

        try:
            async with sse_client(self.server_url, headers=self._get_headers()) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "ollama-chat",
                        arguments={
                            "messages": cleaned_history,
                            "model": model or os.environ.get("MCP_DEFAULT_MODEL", "llama3.2")
                        }
                    )
                    if result and result.content:
                        return result.content[0].text
                    return "(no response content)"
        except Exception as exc:
            logger.error("MCP Chat request failed: %s", exc)
            raise RuntimeError(f"Chat failed: {exc}") from exc

    async def health_check(self) -> dict[str, Any]:
        """Check if the MCP server is reachable and authenticated.

        Returns a dict with 'status' (bool), 'authenticated' (bool), and 'error' (str).
        """
        result = {"status": False, "authenticated": False, "error": ""}
        try:
            # Attempt an authenticated call to verify connectivity and auth
            async with sse_client(self.server_url, headers=self._get_headers()) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    # ollama-list-models is a safe, read-only authorized call
                    await session.call_tool("ollama-list-models")
                    result["status"] = True
                    result["authenticated"] = True
                    return result
        except Exception as exc:
            exc_str = str(exc)
            if "401" in exc_str or "unauthorized" in exc_str.lower() or "403" in exc_str:
                result["status"] = True
                result["authenticated"] = False
                result["error"] = "Authentication failed. Check your API key."
            else:
                result["status"] = False
                result["error"] = f"Server unreachable: {exc_str}"
            return result
