"""Fail-closed API key authentication and bounded per-process rate limiting.

GoreeCloud Identity integration is not implemented. This interim single-key
mechanism is intentionally conservative and not a substitute for a gateway.
"""
import asyncio
import hashlib
import hmac
import os
import time

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

    async def allow(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            if now - self._window_start >= self.window_seconds:
                self._window_start = now
                self._used = 0
            if self._used >= self.limit:
                return False
            self._used += 1
            return True


api_limiter = AccessControl()


async def enforce_api_access(request, call_next):
    if not request.url.path.startswith("/v1/"):
        return await call_next(request)
    configured = os.getenv("CURRENT_API_KEY", "")
    # Fail closed if the secret is missing, weak, or accidentally whitespace.
    if len(configured) < 32 or configured != configured.strip():
        return JSONResponse({"detail": "API authentication not configured"}, status_code=503)
    supplied = request.headers.get("x-api-key", "")
    # Hash both inputs to fixed lengths; avoid timing differences on key length.
    if not hmac.compare_digest(
        hashlib.sha256(supplied.encode("utf-8")).digest(),
        hashlib.sha256(configured.encode("utf-8")).digest(),
    ):
        return JSONResponse(
            {"detail": "Unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if not await api_limiter.allow():
        return JSONResponse(
            {"detail": "Rate limit exceeded"},
            status_code=429,
            headers={"Retry-After": "60"},
        )
    return await call_next(request)
