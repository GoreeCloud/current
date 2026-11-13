"""Atom navigation must select articles, not feed-management or media URLs."""

from current.main import parse_feed


def test_atom_selects_alternate_even_if_self_link_is_first():
    data = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry>'
            b'<link rel="self" href="https://example.org/api/entry/3"/>'
            b'<link rel="alternate" href="https://example.org/article/3"/>'
            b'<title>Article</title></entry></feed>')
    assert parse_feed(data)[0]["link"] == "https://example.org/article/3"


def test_atom_without_alternate_does_not_expose_edit_or_enclosure():
    data = (b'<feed><entry><link rel="edit" href="https://example.org/edit"/>'
            b'<link rel="enclosure" href="https://example.org/audio.mp3"/>'
            b'<title>Article</title></entry></feed>')
    item = parse_feed(data)[0]
    assert item["title"] == "Article"
    assert item["link"] == ""


def test_atom_without_rel_defaults_to_alternate():
    data = b'<feed><entry><link href="https://example.org/article"/></entry></feed>'
    assert parse_feed(data)[0]["link"] == "https://example.org/article"


def test_atom_unsafe_alternate_is_omitted_even_with_safe_edit():
    data = (b'<feed><entry><link rel="edit" href="https://example.org/edit"/>'
            b'<link rel="alternate" href="javascript:alert(1)"/></entry></feed>')
    assert parse_feed(data)[0]["link"] == ""


def test_rss_text_links_continue_to_work():
    data = (b'<rss><channel><item><title>News</title>'
            b'<link>https://example.org/news</link></item></channel></rss>')
    assert parse_feed(data)[0]["link"] == "https://example.org/news"
