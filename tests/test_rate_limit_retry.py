"""Regression tests for precise retry timing under process-global throttling."""
import httpx
import pytest

import current.access as access
from current.main import app


@pytest.mark.asyncio
async def test_retry_after_tracks_remaining_window(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(access.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(access, "api_limiter", access.AccessControl(limit=1, window_seconds=60))
    monkeypatch.setenv("CURRENT_API_KEY", "a" * 40)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        headers = {"x-api-key": "a" * 40}
        assert (await client.get("/v1/feeds", headers=headers)).status_code == 200
        clock[0] = 159.2
        response = await client.get("/v1/feeds", headers=headers)
        assert response.status_code == 429
        assert response.headers["retry-after"] == "1"
        clock[0] = 160.0
        assert (await client.get("/v1/feeds", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_limiter_check_is_atomic_and_never_returns_zero_retry(monkeypatch):
    clock = [500.0]
    monkeypatch.setattr(access.time, "monotonic", lambda: clock[0])
    limiter = access.AccessControl(limit=1, window_seconds=10)
    assert await limiter.check() == (True, 0)
    assert await limiter.check() == (False, 10)
    clock[0] = 509.999
    assert await limiter.check() == (False, 1)
    clock[0] = 510.0
    assert await limiter.check() == (True, 0)
