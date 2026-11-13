"""Exact-host egress allowlist configuration is bounded and fail-closed."""

import pytest
from fastapi import HTTPException

from current import main


@pytest.mark.parametrize("raw", [
    "", "example.org,", ",example.org", "example.org,,other.example",
    "-example.org", "a..example.org", "example.org.",
    "metadata.internal", "service.local", "localhost", "127.0.0.1",
    "example.org\nother.example", "a" * 4097,
    ",".join(["host.example.org"] * 33),
])
def test_malformed_hostname_allowlists_fail_closed(monkeypatch, raw):
    monkeypatch.setenv("CURRENT_FEED_ALLOWED_HOSTS", raw)
    with pytest.raises(HTTPException) as error:
        main.allowed_feed_hosts()
    assert error.value.status_code == 503


def test_normalized_multi_host_allowlist(monkeypatch):
    monkeypatch.setenv("CURRENT_FEED_ALLOWED_HOSTS", " EXAMPLE.ORG, feeds.example.net ")
    assert main.allowed_feed_hosts() == {"example.org", "feeds.example.net"}


@pytest.mark.asyncio
async def test_invalid_allowlist_never_reaches_outbound_feed_request(monkeypatch):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"news":"https://example.org/rss"}')
    monkeypatch.setenv("CURRENT_FEED_EGRESS_GUARDED", "1")
    monkeypatch.setenv("CURRENT_FEED_ALLOWED_HOSTS", "example.org,,other.example")
    async def never_fetch(*args, **kwargs):
        raise AssertionError("Outbound fetch must not run")
    monkeypatch.setattr(main, "get_bounded", never_fetch)
    with pytest.raises(HTTPException) as error:
        await main.read_feed("news")
    assert error.value.status_code == 503
