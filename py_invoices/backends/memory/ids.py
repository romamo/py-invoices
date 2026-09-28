"""Thread-safe ID generation for the in-memory repositories."""

import threading


class IdSequence:
    """Hands out 1, 2, 3, ... exactly once each, even across threads (e.g. API workers)."""

    def __init__(self) -> None:
        self._next = 1
        self._lock = threading.Lock()

    def next(self) -> int:
        with self._lock:
            value = self._next
            self._next += 1
            return value
