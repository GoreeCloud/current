"""Malformed provider data must not enter the in-memory weather cache."""
import json
import pytest
from fastapi import HTTPException
from current import main
from current.cache import BoundedTTLCache


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"current": {}, "daily": {"time": ["2026-11-13"]}},
    {"current": {"temperature_2m": True}, "daily": {"time": ["2026-11-13"]}},
    {"current": {"temperature_2m": "25"}, "daily": {"time": ["2026-11-13"]}},
    {"current": {"temperature_2m": None}, "daily": {"time": ["2026-11-13"]}},
    {"current": {"temperature_2m": 25}, "daily": {}},
    {"current": {"temperature_2m": 25}, "daily": {"time": []}},
    {"current": {"temperature_2m": 25}, "daily": {"time": ["2026-02-30"]}},
    {"current": {"temperature_2m": 25}, "daily": {"time": [1]}},
    {"current": {"temperature_2m": 25}, "daily": {"time": ["2026-11-13", "2026-11-14"]}},
])
async def test_invalid_weather_schema_not_cached(monkeypatch, payload):
    monkeypatch.setattr(main, "weather_cache", BoundedTTLCache())
    calls = 0
    async def fake_fetch(url, *, params=None):
        nonlocal calls
        calls += 1
        return json.dumps(payload).encode()
    monkeypatch.setattr(main, "get_bounded", fake_fetch)
    for _ in range(2):
        with pytest.raises(HTTPException) as err:
            await main.weather(31.1, -87.3, days=1, temperature_unit="celsius")
        assert err.value.status_code == 502
    assert calls == 2


@pytest.mark.asyncio
async def test_valid_negative_temperature_and_date_are_supported(monkeypatch):
    monkeypatch.setattr(main, "weather_cache", BoundedTTLCache())
    async def fake_fetch(url, *, params=None):
        return b'{"current":{"temperature_2m":-4.5},"daily":{"time":["2026-11-13"]}}'
    monkeypatch.setattr(main, "get_bounded", fake_fetch)
    result = await main.weather(41.2, -87.1, days=3, temperature_unit="celsius")
    assert result["current"]["temperature_2m"] == -4.5
