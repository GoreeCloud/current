"""Fail-closed API key authentication and bounded per-process rate limiting.

GoreeCloud Identity integration is not implemented. This interim single-key
mechanism is intentionally conservative and not a substitute for a gateway.
"""
import asyncio
import hashlib
import hmac
import os
import time
import math

from starlette.responses import JSONResponse

class AccessControl:
    def __init__(self, *, limit: int = 60, window_seconds: int = 60):
        if limit < 1 or window_seconds < 1:
            raise ValueError("Limits must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._lock = asyncio.Lock()
        self._window_start = time.monotonic()
        self._used = 0

    async def check(self) -> tuple[bool, int]:
        """Atomically consume quota or report seconds until the window resets."""
        async with self._lock:
            now = time.monotonic()
            if now - self._window_start >= self.window_seconds:
                self._window_start = now
                self._used = 0
            if self._used >= self.limit:
                remaining = max(1, math.ceil(self.window_seconds - (now - self._window_start)))
                return False, remaining
            self._used += 1
            return True, 0

    async def allow(self) -> bool:
        """Compatibility wrapper for existing callers."""
        allowed, _ = await self.check()
        return allowed


api_limiter = AccessControl()


async def enforce_api_access(request, call_next):
    if not request.url.path.startswith("/v1/"):
        return await call_next(request)
    # Weather coordinates and feed selections must not be stored by shared caches.
    private_headers = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}
    configured = os.getenv("CURRENT_API_KEY", "")
    # Fail closed if the secret is missing, weak, or accidentally whitespace.
    if len(configured) < 32 or configured != configured.strip():
        return JSONResponse({"detail": "API authentication not configured"}, status_code=503, headers=private_headers)
    supplied = request.headers.get("x-api-key", "")
    # Hash both inputs to fixed lengths; avoid timing differences on key length.
    if not hmac.compare_digest(
        hashlib.sha256(supplied.encode("utf-8")).digest(),
        hashlib.sha256(configured.encode("utf-8")).digest(),
    ):
        return JSONResponse(
            {"detail": "Unauthorized"},
            status_code=401,
            headers={**private_headers, "WWW-Authenticate": "ApiKey"},
        )
    allowed, retry_after = await api_limiter.check()
    if not allowed:
        return JSONResponse(
            {"detail": "Rate limit exceeded"},
            status_code=429,
            headers={**private_headers, "Retry-After": str(retry_after)},
        )
    response = await call_next(request)
    response.headers.update(private_headers)
    return response
