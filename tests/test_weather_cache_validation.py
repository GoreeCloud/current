"""Ensure malformed weather provider responses never poison the cache."""
import json
import pytest
from fastapi import HTTPException
from current import main
from current.cache import BoundedTTLCache

@pytest.mark.asyncio
async def test_invalid_provider_payload_not_cached(monkeypatch):
    cache = BoundedTTLCache(ttl_seconds=120)
    monkeypatch.setattr(main, "weather_cache", cache)
    calls = 0
    async def fetch(url, *, params=None):
        nonlocal calls
        calls += 1
        if calls == 1:
            return b'{"error":"upstream error"}'
        return json.dumps({"current": {"temperature_2m": 20}, "daily": {"time": ["2026-11-11"]}}).encode()
    monkeypatch.setattr(main, "get_bounded", fetch)
    with pytest.raises(HTTPException) as exc:
        await main.weather(15.123, 17.456, days=3, temperature_unit="celsius")
    assert exc.value.status_code == 502
    result = await main.weather(15.123, 17.456, days=3, temperature_unit="celsius")
    assert result["current"]["temperature_2m"] == 20
    assert calls == 2

@pytest.mark.asyncio
async def test_malformed_json_not_cached(monkeypatch):
    monkeypatch.setattr(main, "weather_cache", BoundedTTLCache())
    calls = 0
    async def fetch(url, *, params=None):
        nonlocal calls
        calls += 1
        return b"not-json"
    monkeypatch.setattr(main, "get_bounded", fetch)
    for _ in range(2):
        with pytest.raises(HTTPException) as exc:
            await main.weather(12.333, 23.444, days=2, temperature_unit="fahrenheit")
        assert exc.value.status_code == 502
    assert calls == 2
