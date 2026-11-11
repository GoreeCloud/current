"""RSS allowlist defense-in-depth and fail-closed tests."""
import pytest
from fastapi import HTTPException
from current import main

@pytest.mark.asyncio
async def test_feed_host_allowlist_fails_closed(monkeypatch):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"news":"https://example.org/rss"}')
    monkeypatch.setenv("CURRENT_FEED_EGRESS_GUARDED", "1")
    monkeypatch.delenv("CURRENT_FEED_ALLOWED_HOSTS", raising=False)
    with pytest.raises(HTTPException) as err:
        await main.read_feed("news")
    assert err.value.status_code == 503

@pytest.mark.asyncio
async def test_feed_host_allowlist_rejects_mismatch(monkeypatch):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"news":"https://example.org/rss"}')
    monkeypatch.setenv("CURRENT_FEED_EGRESS_GUARDED", "1")
    monkeypatch.setenv("CURRENT_FEED_ALLOWED_HOSTS", "another.example")
    with pytest.raises(HTTPException) as err:
        await main.read_feed("news")
    assert err.value.status_code == 503

@pytest.mark.asyncio
async def test_feed_host_allowlist_accepts_exact_host(monkeypatch):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"news":"https://example.org/rss"}')
    monkeypatch.setenv("CURRENT_FEED_EGRESS_GUARDED", "1")
    monkeypatch.setenv("CURRENT_FEED_ALLOWED_HOSTS", " EXAMPLE.ORG ")
    called = []
    async def fake_fetch(url, *, params=None):
        called.append(url)
        return b"<rss><channel><item><title>Ok</title></item></channel></rss>"
    monkeypatch.setattr(main, "get_bounded", fake_fetch)
    result = await main.read_feed("news")
    assert result["items"][0]["title"] == "Ok"
    assert called == ["https://example.org/rss"]
