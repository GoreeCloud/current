"""Bounded, privacy-conscious in-process cache with in-flight deduplication.

No persistent location history is stored. Entries expire by monotonic time,
have a fixed maximum count and payload size, and are isolated to one process.
"""

import asyncio
import time
from collections import OrderedDict
from typing import Awaitable, Callable

class BoundedTTLCache:
    def __init__(self, *, ttl_seconds: int = 120, max_entries: int = 128, max_value_bytes: int = 1_048_576):
        if ttl_seconds <= 0 or max_entries <= 0 or max_value_bytes <= 0:
            raise ValueError("Cache limits must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self.max_value_bytes = max_value_bytes
        self._values: OrderedDict[tuple, tuple[float, bytes]] = OrderedDict()
        self._pending: dict[tuple, asyncio.Task[bytes]] = {}
        self._lock = asyncio.Lock()

    async def get_or_fetch(self, key: tuple, fetch: Callable[[], Awaitable[bytes]]) -> bytes:
        async with self._lock:
            now = time.monotonic()
            item = self._values.get(key)
            if item is not None:
                expires_at, value = item
                if expires_at > now:
                    self._values.move_to_end(key)
                    return value
                del self._values[key]
            task = self._pending.get(key)
            if task is None:
                task = asyncio.create_task(fetch())
                self._pending[key] = task
                # Cleanup is owned by the fetch task, even if all callers cancel.
                task.add_done_callback(lambda completed, k=key: asyncio.create_task(self._complete(k, completed)))
        return await asyncio.shield(task)

    async def _complete(self, key: tuple, task: asyncio.Task[bytes]) -> None:
        async with self._lock:
            if self._pending.get(key) is not task:
                return
            del self._pending[key]
            if task.cancelled():
                return
            try:
                value = task.result()
            except Exception:
                return  # Never cache upstream failures.
            if not isinstance(value, bytes) or len(value) > self.max_value_bytes:
                return
            self._values[key] = (time.monotonic() + self.ttl_seconds, value)
            self._values.move_to_end(key)
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)
