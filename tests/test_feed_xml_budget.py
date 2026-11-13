"""Limit structural complexity of RSS/Atom XML after safe parsing."""

import pytest
from fastapi import HTTPException

from current.main import MAX_FEED_XML_NODES, parse_feed


def test_deep_nested_feed_rejected_with_upstream_error():
    xml = (b"<rss>" + b"<wrapper>" * 33
           + b"<item><title>News</title></item>"
           + b"</wrapper>" * 33 + b"</rss>")
    with pytest.raises(HTTPException) as err:
        parse_feed(xml)
    assert err.value.status_code == 502
    assert err.value.detail == "Invalid RSS or Atom XML"


def test_many_tiny_nodes_rejected_even_below_byte_limit():
    xml = b"<rss>" + b"<item/>" * (MAX_FEED_XML_NODES + 5) + b"</rss>"
    assert len(xml) < 1_048_576
    with pytest.raises(HTTPException) as err:
        parse_feed(xml)
    assert err.value.status_code == 502
    assert err.value.detail == "Invalid RSS or Atom XML"


def test_normal_rss_30_article_cap_preserved():
    xml = b"<rss><channel>" + (
        b"<item><title>Public</title><link>https://example.org/post</link></item>"
        * 40
    ) + b"</channel></rss>"
    items = parse_feed(xml)
    assert len(items) == 30
    assert all(item["title"] == "Public" for item in items)


def test_rss_nodes_at_limit_with_just_one_item():
    xml = b"<rss>" + b"<other/>" * (MAX_FEED_XML_NODES - 3) + (
        b"<item><title>News</title></item></rss>"
    )
    assert len(parse_feed(xml)) == 1
