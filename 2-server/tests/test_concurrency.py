import asyncio
from unittest.mock import patch

import pytest

from mcp_server.config.settings import LLMConfig
from mcp_server.providers.manager import get_provider


@pytest.mark.asyncio
async def test_llm_concurrency_limit():
    """Verify that the ProviderManager correctly limits concurrent LLM requests."""
    # Set limit to 2
    config = LLMConfig(default_model="test-model", max_concurrency=2)
    provider = get_provider(config)

    # Track how many requests were active at the same time
    max_active_observed = 0
    current_active = 0

    async def mock_chat(*args, **kwargs):
        nonlocal current_active, max_active_observed
        current_active += 1
        max_active_observed = max(max_active_observed, current_active)

        # Simulate work
        await asyncio.sleep(0.1)

        current_active -= 1
        return {"content": "ok"}

    # We need to mock the underlying provider's chat method
    # Since ConcurrencyLimitedProvider wraps the original provider
    with patch.object(provider._provider, "chat", side_effect=mock_chat):
        # Fire 5 concurrent requests
        await asyncio.gather(*[provider.chat(messages=[]) for _ in range(5)])

    # Even though we fired 5, the semaphore should have limited it to 2 at a time
    assert max_active_observed == 2
