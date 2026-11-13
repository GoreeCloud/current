"""Operator feed names must map to one unambiguous URL path segment."""

import json

import pytest
from fastapi import HTTPException

from current.main import configured_feeds


@pytest.mark.parametrize("bad_name", [
    "", ".", "..", "../admin", "a/b", "a\\b", "%2fadmin",
    " leading", "trailing ", "news\nother", "news?query", "#feed",
    "a" * 65, "n☃ws",
])
def test_invalid_feed_registry_names_fail_closed(monkeypatch, bad_name):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", json.dumps({
        bad_name: "https://example.org/rss"
    }))
    with pytest.raises(HTTPException) as error:
        configured_feeds()
    assert error.value.status_code == 503
    assert bad_name not in str(error.value.detail)


@pytest.mark.parametrize("good_name", ["news", "tech-weekly", "weather_updates", "a.b", "A1"])
def test_safe_single_segment_feed_names_are_supported(monkeypatch, good_name):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", json.dumps({
        good_name: "https://example.org/rss"
    }))
    assert configured_feeds()[good_name] == "https://example.org/rss"
