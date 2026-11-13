"""Ambiguous authorization headers and URL parsing must fail closed."""

import httpx
import pytest
from fastapi import HTTPException

from current import main
from current.access import AccessControl
import current.access as access


@pytest.mark.asyncio
async def test_duplicate_api_keys_are_rejected_without_consuming_valid_quota(monkeypatch):
    secret = "a" * 40
    monkeypatch.setenv("CURRENT_API_KEY", secret)
    monkeypatch.setenv("CURRENT_FEEDS_JSON", "{}")
    monkeypatch.setattr(access, "api_limiter", AccessControl(limit=1, window_seconds=60))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://testserver"
    ) as client:
        duplicate = await client.get("/v1/feeds", headers=[
            ("X-API-Key", secret), ("x-api-key", "different")
        ])
        assert duplicate.status_code == 401
        assert duplicate.headers["cache-control"] == "no-store"
        assert duplicate.headers["x-content-type-options"] == "nosniff"
        same = await client.get("/v1/feeds", headers=[
            ("X-API-Key", secret), ("X-API-Key", secret)
        ])
        assert same.status_code == 401
        valid = await client.get("/v1/feeds", headers={"X-API-Key": secret})
        assert valid.status_code == 200
        assert (await client.get("/v1/feeds", headers={"X-API-Key": secret})).status_code == 429


@pytest.mark.parametrize("url", [
    r"https://example.org\@untrusted.test/feed",
    r"https://example.org\feed",
])
def test_ambiguous_backslash_feed_sources_are_rejected(monkeypatch, url):
    import json
    monkeypatch.setenv("CURRENT_FEEDS_JSON", json.dumps({"news": url}))
    with pytest.raises(HTTPException) as error:
        main.configured_feeds()
    assert error.value.status_code == 503


@pytest.mark.parametrize("url", [
    r"https://example.org\@untrusted.test/post",
    r"https://example.org\post",
])
def test_ambiguous_backslash_article_urls_are_omitted(url):
    assert main.safe_article_link(url) == ""
