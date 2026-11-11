"""Hostname and HTTP body-boundary regression tests."""
import json
import pytest
import httpx
from fastapi import HTTPException
from current.main import configured_feeds, get_bounded

@pytest.mark.parametrize("host", [
    "-example.org", "example-.org", "foo..org",
    "a" * 64 + ".org", "bad_.org", "example.org.",
])
def test_invalid_dns_labels_rejected(monkeypatch, host):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", json.dumps({"feed": "https://" + host + "/rss"}))
    with pytest.raises(HTTPException) as err:
        configured_feeds()
    assert err.value.status_code == 503

def test_valid_dns_label(monkeypatch):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"feed":"https://rss-1.example.org/feed"}')
    assert configured_feeds()["feed"].startswith("https://rss-1.")

@pytest.mark.asyncio
async def test_oversized_content_length_rejected(monkeypatch):
    original = httpx.AsyncClient
    def fake_client(*args, **kwargs):
        return original(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers={"Content-Length": "999999999"}, content=b"tiny")), **kwargs)
    monkeypatch.setattr(httpx, "AsyncClient", fake_client)
    with pytest.raises(HTTPException) as err:
        await get_bounded("https://example.org/feed")
    assert err.value.status_code == 502

@pytest.mark.asyncio
async def test_invalid_content_length_rejected(monkeypatch):
    original = httpx.AsyncClient
    def fake_client(*args, **kwargs):
        return original(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers={"Content-Length": "bad"}, content=b"tiny")), **kwargs)
    monkeypatch.setattr(httpx, "AsyncClient", fake_client)
    with pytest.raises(HTTPException) as err:
        await get_bounded("https://example.org/feed")
    assert err.value.status_code == 502
