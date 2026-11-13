"""Bound API-key processing and preserve private quota on rejection."""

import httpx
import pytest

import current.access as access
from current.main import app


@pytest.mark.asyncio
async def test_oversized_client_api_key_is_rejected_without_quota(monkeypatch):
    key = "a" * 40
    monkeypatch.setenv("CURRENT_API_KEY", key)
    monkeypatch.setenv("CURRENT_FEEDS_JSON", "{}")
    monkeypatch.setattr(access, "api_limiter", access.AccessControl(limit=1))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as client:
        rejected = await client.get("/v1/feeds", headers={"X-API-Key": "b" * 800})
        assert rejected.status_code == 401
        assert rejected.headers["cache-control"] == "no-store"
        assert (await client.get("/v1/feeds", headers={"X-API-Key": key})).status_code == 200
        assert (await client.get("/v1/feeds", headers={"X-API-Key": key})).status_code == 429


@pytest.mark.asyncio
async def test_oversized_operator_secret_fails_closed(monkeypatch):
    monkeypatch.setenv("CURRENT_API_KEY", "a" * 513)
    monkeypatch.setenv("CURRENT_FEEDS_JSON", "{}")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as client:
        assert (await client.get("/readyz")).status_code == 503
        assert (await client.get("/v1/feeds", headers={"X-API-Key": "a" * 513})).status_code == 503


def test_configured_key_rejects_excess_utf8_byte_count(monkeypatch):
    monkeypatch.setenv("CURRENT_API_KEY", "é" * 300)
    assert access.configured_api_key() is None
    monkeypatch.setenv("CURRENT_API_KEY", "z" * 512)
    assert access.configured_api_key() == "z" * 512
