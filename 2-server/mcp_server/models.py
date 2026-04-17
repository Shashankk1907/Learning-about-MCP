"""Shared Pydantic models for tool input/output."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EchoInput(BaseModel):
    """Input for the echo tool."""
    message: str = Field(..., max_length=1000, description="The message to echo")


class ChatMessage(BaseModel):
    """A single message in a chat conversation."""
    role: str = Field(..., pattern="^(user|assistant|system|tool)$")
    content: str | None = Field(default=None, max_length=10000)
    tool_calls: list[dict[str, Any]] | None = Field(default=None)
    tool_call_id: str | None = Field(default=None)


class ChatInput(BaseModel):
    """Input for the chat tool."""
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=20)
    model: str | None = Field(default=None, pattern="^[a-zA-Z0-9:._-]+$")
