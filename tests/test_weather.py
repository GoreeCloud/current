"""Weather API contract and upstream-failure regression tests."""
import json
import pytest
from fastapi import HTTPException
from current import main


@pytest.mark.asyncio
async def test_weather_units_days(monkeypatch):
    observed = {}
    async def fake_get(url, *, params=None):
        observed.update(params)
        return json.dumps({"current": {"temperature_2m": 72}, "daily": {"time": ["2026-11-11"]}}).encode()
    monkeypatch.setattr(main, "get_bounded", fake_get)
    result = await main.weather(40.0, -74.0, days=3, temperature_unit="fahrenheit")
    assert result["current"]["temperature_2m"] == 72
    assert observed["forecast_days"] == 3
    assert observed["temperature_unit"] == "fahrenheit"


@pytest.mark.asyncio
async def test_weather_rejects_unexpected_upstream(monkeypatch):
    async def fake_get(url, *, params=None):
        return b'{"error":"upstream error"}'
    monkeypatch.setattr(main, "get_bounded", fake_get)
    with pytest.raises(HTTPException) as error:
        await main.weather(40.0, -74.0, days=5, temperature_unit="celsius")
    assert error.value.status_code == 502


@pytest.mark.asyncio
async def test_weather_rejects_nonfinite_coordinates():
    with pytest.raises(HTTPException) as error:
        await main.weather(float("nan"), -74.0, days=5, temperature_unit="celsius")
    assert error.value.status_code == 422
