import pytest
from fastapi import HTTPException
from current.main import configured_feeds, parse_feed, read_feed


def test_rss_parse():
    xml = b"<rss><channel><item><title>Example</title><link>https://example.org/a</link></item></channel></rss>"
    assert parse_feed(xml)[0]["title"] == "Example"


def test_atom_parse():
    xml = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>News</title><link href="https://example.org"/></entry></feed>'
    assert parse_feed(xml)[0]["link"] == "https://example.org"


def test_entity_blocked():
    with pytest.raises(Exception):
        parse_feed(b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss><item>&x;</item></rss>')


def test_registry(monkeypatch):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"news":"https://example.org/rss"}')
    assert configured_feeds()["news"] == "https://example.org/rss"


def test_registry_rejects_duplicate_feed_names(monkeypatch):
    monkeypatch.setenv(
        "CURRENT_FEEDS_JSON",
        '{"news":"https://example.org/a","news":"https://example.org/b"}',
    )
    with pytest.raises(HTTPException) as exc:
        configured_feeds()
    assert exc.value.status_code == 503
    assert "example.org" not in str(exc.value.detail)


def test_registry_rejects_duplicate_nested_json_keys(monkeypatch):
    monkeypatch.setenv(
        "CURRENT_FEEDS_JSON",
        '{"news":"https://example.org/a","meta":{"x":1,"x":2}}',
    )
    with pytest.raises(HTTPException) as exc:
        configured_feeds()
    assert exc.value.status_code == 503


@pytest.mark.parametrize("url", [
    "http://example.org/rss", "https://127.0.0.1/rss",
    "https://169.254.169.254/rss", "https://metadata.internal/rss",
    "https://example.org:8443/rss", "https://user:password@example.org/rss",
    "https://example.org:bad/rss", "https://example.org/rss#fragment",
])
def test_registry_rejects_unsafe_urls(monkeypatch, url):
    import json
    monkeypatch.setenv("CURRENT_FEEDS_JSON", json.dumps({"unsafe": url}))
    with pytest.raises(HTTPException) as exc:
        configured_feeds()
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_feed_fetch_fails_closed(monkeypatch):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"news":"https://example.org/rss"}')
    monkeypatch.delenv("CURRENT_FEED_EGRESS_GUARDED", raising=False)
    with pytest.raises(HTTPException) as exc:
        await read_feed("news")
    assert exc.value.status_code == 503
