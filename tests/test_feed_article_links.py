"""Untrusted RSS links are display data, never executable navigation schemes."""
import pytest
from fastapi import HTTPException
from current.main import parse_feed, safe_article_link


@pytest.mark.parametrize("link", [
    "javascript:alert(1)", "data:text/html,hello", "file:///etc/passwd",
    "//example.org/path", "/relative/path", "https://user:pass@example.org/x",
    "https://example.org:bad/x", "https://example.org/\nheader",
    "https://example.org/" + "x" * 2100,
])
def test_unsafe_article_links_are_omitted(link):
    assert safe_article_link(link) == ""


@pytest.mark.parametrize("link", [
    "https://example.org/article?x=1", "http://example.org/article",
    "https://example.org:443/article",
])
def test_absolute_article_links_are_preserved(link):
    assert safe_article_link(link) == link


def test_rss_drops_unsafe_link_but_preserves_item_content():
    items = parse_feed(
        b"<rss><channel><item><title>Safe title</title>"
        b"<link>javascript:alert(1)</link></item></channel></rss>"
    )
    assert items[0]["title"] == "Safe title"
    assert items[0]["link"] == ""


def test_atom_unsafe_href_is_omitted():
    items = parse_feed(
        b'<feed><entry><title>Entry</title><link href="data:text/html,bad"/></entry></feed>'
    )
    assert items[0]["link"] == ""


def test_feed_returns_at_most_thirty_items():
    payload = b"<rss><channel>" + b"<item><title>x</title></item>" * 50 + b"</channel></rss>"
    assert len(parse_feed(payload)) == 30


def test_oversized_feed_body_fails_closed():
    with pytest.raises(HTTPException) as exc:
        parse_feed(b"x" * 1_048_577)
    assert exc.value.status_code == 502
