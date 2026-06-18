"""
rate_limiter.py — Thread-safe token bucket rate limiter with exponential backoff.

Two separate limiters guard Reddit API calls and Anthropic API calls so neither
service gets hammered even if one is fast and the other is slow.
"""

import time
import threading
import random
from functools import wraps


class TokenBucketLimiter:
    """
    Thread-safe token bucket rate limiter.

    Tokens refill continuously at `requests_per_minute / 60` tokens per second.
    `burst_size` controls how many back-to-back requests are allowed before
    throttling kicks in (defaults to 10% of the per-minute limit, min 3).
    """

    def __init__(self, requests_per_minute: int, burst_size: int = None):
        self.rpm          = requests_per_minute
        self.burst_size   = burst_size or max(3, requests_per_minute // 10)
        self.tokens       = float(self.burst_size)
        self.refill_rate  = requests_per_minute / 60.0   # tokens / second
        self.last_refill  = time.monotonic()
        self._lock        = threading.Lock()

    # ------------------------------------------------------------------ #
    def _refill(self):
        now      = time.monotonic()
        elapsed  = now - self.last_refill
        self.tokens       = min(self.burst_size, self.tokens + elapsed * self.refill_rate)
        self.last_refill  = now

    def acquire(self, timeout: float = 120.0) -> bool:
        """Block until a token is available, or raise TimeoutError."""
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return True

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"Rate limiter: could not acquire token within {timeout}s "
                    f"({self.rpm} req/min limit)."
                )
            # Wait for roughly the time it takes to earn one token
            sleep_for = min(remaining, max(0.1, 1.0 / self.refill_rate))
            time.sleep(sleep_for)

    def status(self) -> dict:
        with self._lock:
            self._refill()
            return {
                "tokens_available": round(self.tokens, 2),
                "burst_size":       self.burst_size,
                "requests_per_min": self.rpm,
            }


# ------------------------------------------------------------------ #

def exponential_backoff(max_retries: int = 5, base_delay: float = 1.0,
                        max_delay: float = 64.0, exceptions=(Exception,)):
    """
    Decorator: retry with exponential backoff + jitter on failure.

    Each retry waits  min(base_delay * 2^attempt + jitter, max_delay)  seconds.
    After `max_retries` failures the last exception is re-raised.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_retries - 1:
                        raise
                    delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                    print(f"  ↻ Attempt {attempt + 1} failed ({type(exc).__name__}: {exc}). "
                          f"Retrying in {delay:.1f}s …")
                    time.sleep(delay)
        return wrapper
    return decorator


# ------------------------------------------------------------------ #

class RateLimitManager:
    """Registry of named rate limiters — one per external API."""

    def __init__(self):
        self._limiters: dict[str, TokenBucketLimiter] = {}

    def register(self, name: str, requests_per_minute: int, burst_size: int = None):
        self._limiters[name] = TokenBucketLimiter(requests_per_minute, burst_size)
        return self

    def wait(self, api: str):
        """Block until the named API's limiter has a free token."""
        if api not in self._limiters:
            raise KeyError(f"No rate limiter registered for '{api}'")
        self._limiters[api].acquire()

    def status(self) -> dict:
        return {name: lim.status() for name, lim in self._limiters.items()}
