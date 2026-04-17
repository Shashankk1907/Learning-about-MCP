"""In-memory token-bucket rate limiter.

Each identity gets its own bucket. Tokens replenish at a fixed rate per minute.
Thread-safe for use within a single async event loop (no locking needed).
"""
from __future__ import annotations

import time
from collections import defaultdict


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


class RateLimiter:
    """Token-bucket rate limiter keyed on identity label.

    Args:
        requests_per_minute: Maximum number of requests allowed per minute per identity.
    """

    def __init__(self, requests_per_minute: int = 60) -> None:
        self._rpm = requests_per_minute
        self._refill_rate = requests_per_minute / 60.0   # tokens per second
        # {label: (tokens_remaining, last_checked_timestamp)}
        self._buckets: dict[str, tuple[float, float]] = defaultdict(
            lambda: (float(requests_per_minute), time.monotonic())
        )

    def check(self, identity_label: str) -> None:
        """Consume one token for *identity_label*.

        Raises:
            RateLimitExceeded: when the bucket is empty.
        """
        tokens, last_time = self._buckets[identity_label]
        now = time.monotonic()
        elapsed = now - last_time

        # Refill based on elapsed time.
        tokens = min(float(self._rpm), tokens + elapsed * self._refill_rate)

        if tokens < 1.0:
            raise RateLimitExceeded(f"Rate limit exceeded: max {self._rpm} requests/minute")

        self._buckets[identity_label] = (tokens - 1.0, now)
