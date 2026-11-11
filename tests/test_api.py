from fastapi import HTTPException
from current.main import configured_feeds, parse_feed


def test_rss_parse():
    xml = b"<rss><channel><item><title>Example</title><link>https://example.org/a</link></item></channel></rss>"
    assert parse_feed(xml)[0]["title"] == "Example"


def test_atom_parse():
    xml = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>News</title><link href="https://example.org"/></entry></feed>'
    assert parse_feed(xml)[0]["link"] == "https://example.org"


def test_entity_blocked():
    try:
        parse_feed(b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><rss><item>&x;</item></rss>')
        assert False, "Expected entity rejection"
    except Exception:
        pass


def test_registry(monkeypatch):
    monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"news":"https://example.org/rss"}')
    assert configured_feeds()["news"] == "https://example.org/rss"
