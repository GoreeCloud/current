"""Noncanonical numeric hostnames must not bypass the RSS DNS-name policy."""

import json

import pytest
from fastapi import HTTPException

from current import main


@pytest.mark.parametrize("host", [
    "127.1", "127.0.1", "127.000.000.001", "0177.0.0.1",
    "0x7f.0.0.1", "0X7f.0.0.1", "0x7f.1",
    "2130706433", "0x7f000001", "00000000177.0.0.1",
])
def test_noncanonical_numeric_source_hosts_fail_closed(monkeypatch, host):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", json.dumps({
        "news": f"https://{host}/feed",
    }))
    with pytest.raises(HTTPException) as error:
        main.configured_feeds()
    assert error.value.status_code == 503


@pytest.mark.parametrize("host", [
    "127.1", "127.0.1", "0177.0.0.1",
    "0x7f.1", "0X7f.0.0.1", "2130706433",
])
def test_noncanonical_numeric_allowlist_hosts_fail_closed(monkeypatch, host):
    monkeypatch.setenv("CURRENT_FEED_ALLOWED_HOSTS", host)
    with pytest.raises(HTTPException) as error:
        main.allowed_feed_hosts()
    assert error.value.status_code == 503


def test_valid_dns_labels_and_public_subdomains_still_work(monkeypatch):
    monkeypatch.setenv(
        "CURRENT_FEEDS_JSON",
        json.dumps({"news": "https://127.1.example.org/feed"}),
    )
    monkeypatch.setenv("CURRENT_FEED_ALLOWED_HOSTS", "127.1.example.org")
    assert main.configured_feeds()["news"] == "https://127.1.example.org/feed"
    assert main.allowed_feed_hosts() == {"127.1.example.org"}
    assert not main.numeric_host_alias("127.1.example.org")


@pytest.mark.asyncio
async def test_rejected_numeric_source_never_fetched(monkeypatch):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"news":"https://127.1/rss"}')
    monkeypatch.setenv("CURRENT_FEED_ALLOWED_HOSTS", "127.1")
    monkeypatch.setenv("CURRENT_FEED_EGRESS_GUARDED", "1")

    async def never_fetch(*args, **kwargs):
        raise AssertionError("Network fetch must not occur")

    monkeypatch.setattr(main, "get_bounded", never_fetch)
    with pytest.raises(HTTPException) as error:
        await main.read_feed("news")
    assert error.value.status_code == 503
