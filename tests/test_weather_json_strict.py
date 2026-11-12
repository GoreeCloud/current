"""Reject invalid JSON constants before they enter the weather cache."""
import pytest
from fastapi import HTTPException

from current import main
from current.cache import BoundedTTLCache


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [b'NaN', b'Infinity', b'-Infinity'])
async def test_nonfinite_upstream_numbers_are_not_cached(monkeypatch, invalid):
    monkeypatch.setattr(main, "weather_cache", BoundedTTLCache())
    calls = 0

    async def fetch(url, *, params=None):
        nonlocal calls
        calls += 1
        return b'{"current":{"temperature_2m":' + invalid + b'},"daily":{"time":[]}}'

    monkeypatch.setattr(main, "get_bounded", fetch)
    for _ in range(2):
        with pytest.raises(HTTPException) as error:
            await main.weather(12.5, 34.5, days=2, temperature_unit="celsius")
        assert error.value.status_code == 502
    assert calls == 2


@pytest.mark.asyncio
async def test_deeply_nested_weather_json_fails_as_upstream_error(monkeypatch):
    monkeypatch.setattr(main, "weather_cache", BoundedTTLCache())
    calls = 0

    async def fetch(url, *, params=None):
        nonlocal calls
        calls += 1
        return b'[' * 1500 + b'0' + b']' * 1500

    monkeypatch.setattr(main, "get_bounded", fetch)
    for _ in range(2):
        with pytest.raises(HTTPException) as error:
            await main.weather(11.5, 21.5, days=2, temperature_unit="celsius")
        assert error.value.status_code == 502
    assert calls == 2
