"""Completed fetches clear pending state without scheduling extra turns."""

import asyncio

import pytest

from current.cache import BoundedTTLCache


@pytest.mark.asyncio
async def test_immediate_retry_after_provider_error_creates_new_fetch():
    cache = BoundedTTLCache()
    attempts = 0

    async def flaky():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("synthetic provider failure")
        return b"recovered"

    with pytest.raises(RuntimeError):
        await cache.get_or_fetch(("location",), flaky)
    assert not cache._pending
    assert await cache.get_or_fetch(("location",), flaky) == b"recovered"
    assert attempts == 2
    assert not cache._pending
    assert cache._values[("location",)][1] == b"recovered"


@pytest.mark.asyncio
async def test_first_success_is_immediately_available_without_extra_event_loop_turn():
    cache = BoundedTTLCache()
    attempts = 0

    async def fetch():
        nonlocal attempts
        attempts += 1
        return b"weather"

    assert await cache.get_or_fetch(("same-location",), fetch) == b"weather"
    assert not cache._pending
    assert await cache.get_or_fetch(("same-location",), fetch) == b"weather"
    assert attempts == 1


@pytest.mark.asyncio
async def test_one_canceled_waiter_does_not_cancel_shared_fetch():
    cache = BoundedTTLCache()
    started, release = asyncio.Event(), asyncio.Event()
    attempts = 0

    async def fetch():
        nonlocal attempts
        attempts += 1
        started.set()
        await release.wait()
        return b"shared"

    first = asyncio.create_task(cache.get_or_fetch(("shared",), fetch))
    await started.wait()
    second = asyncio.create_task(cache.get_or_fetch(("shared",), fetch))
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    release.set()
    assert await second == b"shared"
    assert attempts == 1
    assert not cache._pending
