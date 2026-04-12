"""Simple in-process API rate limiter."""

from __future__ import annotations

import threading
import time
from collections import deque


class RequestRateLimiter:
    """Allow at most `max_requests` in a rolling `window_seconds` period."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max(1, int(max_requests))
        self.window_seconds = max(1.0, float(window_seconds))
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                cutoff = now - self.window_seconds
                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return

                sleep_for = self.window_seconds - (now - self._timestamps[0]) + 0.01
            time.sleep(max(0.01, sleep_for))
