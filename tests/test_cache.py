"""Cache isolation, coalescing, boundedness and failure behavior tests."""
import asyncio
import pytest
from current.cache import BoundedTTLCache


@pytest.mark.asyncio
async def test_cache_hit_and_key_isolation():
    cache = BoundedTTLCache(ttl_seconds=10)
    calls = 0
    async def fetch():
        nonlocal calls
        calls += 1
        return str(calls).encode()
    assert await cache.get_or_fetch(("a",), fetch) == b"1"
    await asyncio.sleep(0)  # Permit the completion callback to cache the result.
    await asyncio.sleep(0)
    assert await cache.get_or_fetch(("a",), fetch) == b"1"
    assert await cache.get_or_fetch(("b",), fetch) == b"2"
    assert calls == 2


@pytest.mark.asyncio
async def test_singleflight_concurrent_callers():
    cache = BoundedTTLCache()
    calls = 0
    async def fetch():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return b"shared"
    results = await asyncio.gather(*(cache.get_or_fetch(("same",), fetch) for _ in range(20)))
    assert results == [b"shared"] * 20
    assert calls == 1


@pytest.mark.asyncio
async def test_failure_not_cached():
    cache = BoundedTTLCache()
    calls = 0
    async def fetch():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError("provider down")
        return b"recovered"
    with pytest.raises(ValueError):
        await cache.get_or_fetch(("x",), fetch)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert await cache.get_or_fetch(("x",), fetch) == b"recovered"


@pytest.mark.asyncio
async def test_eviction_and_oversized_payloads():
    cache = BoundedTTLCache(max_entries=1, max_value_bytes=4)
    calls = 0
    async def fetch():
        nonlocal calls
        calls += 1
        return b"large" if calls == 1 else b"ok"
    assert await cache.get_or_fetch(("a",), fetch) == b"large"
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert await cache.get_or_fetch(("a",), fetch) == b"ok"
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert await cache.get_or_fetch(("b",), fetch) == b"ok"
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert len(cache._values) <= 1
