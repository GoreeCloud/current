"""Regression tests for capacity pressure and hostile feed XML."""
import asyncio
import pytest
from fastapi import HTTPException
from current.cache import BoundedTTLCache, CacheBusyError
from current.main import parse_feed


@pytest.mark.asyncio
async def test_distinct_upstream_requests_bounded():
    cache = BoundedTTLCache(max_entries=1)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow():
        started.set()
        await release.wait()
        return b"ok"

    first = asyncio.create_task(cache.get_or_fetch(("first",), slow))
    await started.wait()
    with pytest.raises(CacheBusyError):
        await cache.get_or_fetch(("second",), slow)
    release.set()
    assert await first == b"ok"


def test_hostile_entity_is_sanitized_error():
    xml = b'<!DOCTYPE rss [<!ENTITY leak SYSTEM "file:///etc/passwd">]><rss><channel><item><title>&leak;</title></item></channel></rss>'
    with pytest.raises(HTTPException) as exc:
        parse_feed(xml)
    assert exc.value.status_code == 502
    assert exc.value.detail == "Invalid RSS or Atom XML"


def test_malformed_xml_is_sanitized_error():
    with pytest.raises(HTTPException) as exc:
        parse_feed(b"<rss><channel><item></rss>")
    assert exc.value.status_code == 502
