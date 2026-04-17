"""LLM-related tools for the MCP server."""
from __future__ import annotations

import json
from typing import Any

from mcp.server.lowlevel.server import request_ctx

from mcp_server.core.app import SecureMCP
from mcp_server.models import ChatMessage
from mcp_server.providers.base import LLMProvider


def register_llm_tools(app: SecureMCP, provider: LLMProvider):
    """Register LLM tools with the SecureMCP application."""

    def _get_available_tools() -> list[dict[str, Any]]:
        """Discover all available tools in the MCP app and format them for the LLM."""
        tools = []
        # Access the underlying FastMCP tool manager
        for tool_info in app._mcp._tool_manager.list_tools():
            # Exclude LLM-related tools to avoid recursion/redundancy
            if tool_info.name in ["ollama-chat", "ollama-list-models"]:
                continue

            tools.append({
                "type": "function",
                "function": {
                    "name": tool_info.name,
                    "description": tool_info.description,
                    "parameters": tool_info.parameters
                }
            })
        return tools

    @app.tool(
        name="ollama-chat",
        description="Send a chat message to the local LLM with tool-calling capabilities",
        required_scopes=["tools:ollama:chat"]
    )
    async def ollama_chat(
        messages: list[ChatMessage],
        model: str | None = None
    ) -> str:
        # Retrieve the identity of the original caller from the current request context
        # This ensures we don't allow a "Confused Deputy" attack where the LLM
        # executes tools the caller isn't authorized for.
        try:
            ctx = request_ctx.get()
            identity = app.auth.get_identity(ctx)
        except LookupError:
            return "Error: Request context not found. Cannot verify authorization."
        except Exception as e:
            return f"Error resolving identity: {str(e)}"

        # Prepare initial messages for the LLM
        raw_messages = [m.model_dump(exclude_none=True) for m in messages]
        available_tools = _get_available_tools()

        # Iterative tool-calling loop (max 5 iterations)
        for _ in range(5):
            response_msg = await provider.chat(
                messages=raw_messages,
                tools=available_tools if available_tools else None,
                model=model,
            )

            # Add assistant's response to the conversation history
            raw_messages.append(response_msg)

            tool_calls = response_msg.get("tool_calls")
            if not tool_calls:
                # No more tool calls, we have the final answer
                return response_msg.get("content", "(no response)")

            # Execute each tool call requested by the LLM
            for tool_call in tool_calls:
                function = tool_call.get("function", {})
                tool_name = function.get("name")
                tool_args = function.get("arguments")
                tool_call_id = tool_call.get("id")

                try:
                    # Call the tool through the MCP application with identity enforcement
                    tool_result = await app.call_tool_secure(tool_name, tool_args, identity)

                    # Extract text content from the MCP result
                    result_text = ""
                    if hasattr(tool_result, "content"):
                        result_text = "\n".join(c.text for c in tool_result.content if hasattr(c, "text"))
                    elif isinstance(tool_result, list):
                        result_text = "\n".join(str(c) for c in tool_result)
                    else:
                        result_text = str(tool_result)

                    raw_messages.append({
                        "role": "tool",
                        "content": result_text,
                        "tool_call_id": tool_call_id
                    })
                except Exception as e:
                    raw_messages.append({
                        "role": "tool",
                        "content": f"Error executing tool {tool_name}: {str(e)}"
                    })

        return "Error: Maximum tool-call iterations reached."

    @app.tool(
        name="ollama-list-models",
        description="List all locally available models",
        required_scopes=["tools:ollama:list"]
    )
    async def list_models() -> str:
        models = await provider.list_models()
        return json.dumps(models)
