"""Unsafe private-network navigation URLs from feeds must not reach clients."""
import pytest
from current.main import safe_article_link, parse_feed


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/admin",
    "http://127.1/admin",
    "https://169.254.169.254/latest/meta-data/",
    "http://192.168.1.1/",
    "http://10.0.0.1/",
    "https://[::1]/",
    "http://[fd00::1]/private",
    "http://localhost/",
    "https://localhost./",
    "http://service.local/",
    "http://metadata.internal/secret",
    "https://gateway.localhost/admin",
])
def test_local_and_literal_ip_links_are_omitted(url):
    assert safe_article_link(url) == ""


@pytest.mark.parametrize("url", [
    "http://news.example.org/article",
    "https://news.example.org/article?id=42",
    "https://news.example.org:443/article",
])
def test_public_dns_article_urls_still_work(url):
    assert safe_article_link(url) == url


def test_rss_local_link_is_removed_without_losing_title():
    xml = (b"<rss><channel><item><title>Public headline</title>"
           b"<link>http://127.0.0.1/admin</link></item></channel></rss>")
    item = parse_feed(xml)[0]
    assert item["title"] == "Public headline"
    assert item["link"] == ""
