"""Expired weather location cache entries are removed on unrelated traffic."""

import time

import pytest

from current.cache import BoundedTTLCache


@pytest.mark.asyncio
async def test_unrelated_new_location_prunes_all_expired_cached_coordinates():
    cache = BoundedTTLCache(ttl_seconds=120, max_entries=4)
    now = time.monotonic()
    cache._values[("expired-location-a",)] = (now - 5, b"old-a")
    cache._values[("expired-location-b",)] = (now, b"old-b")
    cache._values[("still-live-location",)] = (now + 60, b"valid")

    calls = 0

    async def fetch():
        nonlocal calls
        calls += 1
        return b"new"

    assert await cache.get_or_fetch(("new-location",), fetch) == b"new"
    assert ("expired-location-a",) not in cache._values
    assert ("expired-location-b",) not in cache._values
    assert cache._values[("still-live-location",)][1] == b"valid"
    assert calls == 1


@pytest.mark.asyncio
async def test_live_cache_hit_also_prunes_unrelated_expired_location():
    cache = BoundedTTLCache(ttl_seconds=120)
    now = time.monotonic()
    cache._values[("expired-location",)] = (now - 1, b"stale")
    cache._values[("live-location",)] = (now + 20, b"saved")
    async def should_not_fetch():
        raise AssertionError("live cache hit must not trigger a fetch")
    assert await cache.get_or_fetch(("live-location",), should_not_fetch) == b"saved"
    assert list(cache._values) == [("live-location",)]
