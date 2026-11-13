"""Readiness reports invalid enabled RSS configuration without disclosing URLs."""

import httpx
import pytest

from current.main import app

KEY = "r" * 40


@pytest.mark.asyncio
async def test_readiness_checks_guarded_feed_allowlist(monkeypatch):
    monkeypatch.setenv("CURRENT_API_KEY", KEY)
    monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"news":"https://example.org/rss"}')
    monkeypatch.setenv("CURRENT_FEED_EGRESS_GUARDED", "1")
    monkeypatch.delenv("CURRENT_FEED_ALLOWED_HOSTS", raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as client:
        invalid = await client.get("/readyz")
        assert invalid.status_code == 503
        assert "example.org" not in invalid.text
        monkeypatch.setenv("CURRENT_FEED_ALLOWED_HOSTS", "other.example")
        invalid = await client.get("/readyz")
        assert invalid.status_code == 503
        monkeypatch.setenv("CURRENT_FEED_ALLOWED_HOSTS", "EXAMPLE.ORG")
        ready = await client.get("/readyz")
        assert ready.status_code == 200
        assert ready.json() == {"status": "ready", "service": "GoreeCloud Current"}


@pytest.mark.asyncio
async def test_default_disabled_rss_keeps_local_config_ready(monkeypatch):
    monkeypatch.setenv("CURRENT_API_KEY", KEY)
    monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"news":"https://example.org/rss"}')
    monkeypatch.delenv("CURRENT_FEED_EGRESS_GUARDED", raising=False)
    monkeypatch.delenv("CURRENT_FEED_ALLOWED_HOSTS", raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://testserver") as client:
        assert (await client.get("/readyz")).status_code == 200
