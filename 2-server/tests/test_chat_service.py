from unittest.mock import AsyncMock, patch

import pytest
from mcp import types

from ui.chat_service import ChatService


@pytest.fixture
def chat_service():
    # Use default settings
    return ChatService()

@pytest.mark.asyncio
async def test_chat_truncation(chat_service):
    """Verify that only the latest 10 messages are sent to the tool."""
    # Create 15 messages
    messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"} for i in range(15)]

    # Mock sse_client
    mock_sse_cm = AsyncMock()
    mock_sse_cm.__aenter__.return_value = (AsyncMock(), AsyncMock())

    # Mock ClientSession
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session

    mock_result = types.CallToolResult(content=[types.TextContent(type="text", text="hello")])
    mock_session.call_tool = AsyncMock(return_value=mock_result)

    with patch("ui.chat_service.sse_client", return_value=mock_sse_cm), \
         patch("ui.chat_service.ClientSession", return_value=mock_session):

        await chat_service.chat(messages, model="test-model")

        # Verify call_tool was called
        mock_session.call_tool.assert_called_once()
        args = mock_session.call_tool.call_args.kwargs["arguments"]["messages"]
        assert len(args) == 10
        assert args[0]["content"] == "msg 5"
        assert args[-1]["content"] == "msg 14"

@pytest.mark.asyncio
async def test_chat_short_history(chat_service):
    """Verify that short history is sent untouched."""
    messages = [{"role": "user", "content": "hi"}]

    mock_sse_cm = AsyncMock()
    mock_sse_cm.__aenter__.return_value = (AsyncMock(), AsyncMock())

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session

    mock_result = types.CallToolResult(content=[types.TextContent(type="text", text="hello")])
    mock_session.call_tool = AsyncMock(return_value=mock_result)

    with patch("ui.chat_service.sse_client", return_value=mock_sse_cm), \
         patch("ui.chat_service.ClientSession", return_value=mock_session):

        await chat_service.chat(messages)

        mock_session.call_tool.assert_called_once()
        args = mock_session.call_tool.call_args.kwargs["arguments"]["messages"]
        assert len(args) == 1
        assert args[0]["content"] == "hi"

@pytest.mark.asyncio
async def test_list_models_success(chat_service):
    """Verify models are listed correctly."""
    mock_sse_cm = AsyncMock()
    mock_sse_cm.__aenter__.return_value = (AsyncMock(), AsyncMock())

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session

    mock_result = types.CallToolResult(content=[types.TextContent(type="text", text='["model1", "model2"]')])
    mock_session.call_tool = AsyncMock(return_value=mock_result)

    with patch("ui.chat_service.sse_client", return_value=mock_sse_cm), \
         patch("ui.chat_service.ClientSession", return_value=mock_session):

        models = await chat_service.list_models()
        assert models == ["model1", "model2"]

@pytest.mark.asyncio
async def test_health_check_success(chat_service):
    """Verify health check success scenario."""
    mock_sse_cm = AsyncMock()
    mock_sse_cm.__aenter__.return_value = (AsyncMock(), AsyncMock())

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.initialize = AsyncMock()
    mock_session.call_tool = AsyncMock()

    with patch("ui.chat_service.sse_client", return_value=mock_sse_cm), \
         patch("ui.chat_service.ClientSession", return_value=mock_session):

        result = await chat_service.health_check()
        assert result["status"] is True
        assert result["authenticated"] is True
        assert result["error"] == ""

@pytest.mark.asyncio
async def test_health_check_auth_failure(chat_service):
    """Verify health check handling of authentication failure."""
    mock_sse_cm = AsyncMock()
    # Mocking sse_client to raise a "401 Unauthorized" error when used
    mock_sse_cm.__aenter__.side_effect = Exception("401 Unauthorized")

    with patch("ui.chat_service.sse_client", return_value=mock_sse_cm):
        result = await chat_service.health_check()
        assert result["status"] is True
        assert result["authenticated"] is False
        assert "Authentication failed" in result["error"]

@pytest.mark.asyncio
async def test_health_check_unreachable(chat_service):
    """Verify health check handling of unreachable server."""
    mock_sse_cm = AsyncMock()
    mock_sse_cm.__aenter__.side_effect = Exception("Connection refused")

    with patch("ui.chat_service.sse_client", return_value=mock_sse_cm):
        result = await chat_service.health_check()
        assert result["status"] is False
        assert result["authenticated"] is False
        assert "Server unreachable" in result["error"]
