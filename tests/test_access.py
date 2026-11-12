"""HTTP-level access control regression tests."""
import pytest
import httpx

from current.main import app
from current.access import AccessControl
import current.access as access

KEY = "a" * 40

@pytest.fixture
def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")

@pytest.mark.asyncio
async def test_documentation_routes_are_not_public_by_default(client):
    # OpenAPI and interactive docs must not bypass the /v1 API-key gate.
    from current.main import _DOCS_ENABLED
    assert not _DOCS_ENABLED
    async with client as c:
        for path in ("/docs", "/redoc", "/openapi.json"):
            response = await c.get(path)
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_is_public_when_unconfigured(client, monkeypatch):
    monkeypatch.delenv("CURRENT_API_KEY", raising=False)
    async with client as c:
        response = await c.get("/healthz")
        assert response.status_code == 200
        response = await c.get("/v1/feeds")
        assert response.status_code == 503

@pytest.mark.asyncio
async def test_readiness_requires_valid_key_and_feed_registry(client, monkeypatch):
    monkeypatch.delenv("CURRENT_API_KEY", raising=False)
    async with client as c:
        assert (await c.get("/healthz")).status_code == 200
        assert (await c.get("/readyz")).status_code == 503
        monkeypatch.setenv("CURRENT_API_KEY", KEY)
        monkeypatch.setenv("CURRENT_FEEDS_JSON", "{bad-json")
        invalid = await c.get("/readyz")
        assert invalid.status_code == 503
        assert "bad-json" not in invalid.text
        monkeypatch.setenv("CURRENT_FEEDS_JSON", '{"news":"https://example.org/rss"}')
        ready = await c.get("/readyz")
        assert ready.status_code == 200
        assert ready.json() == {"status": "ready", "service": "GoreeCloud Current"}
        assert "news" not in ready.text


@pytest.mark.asyncio
async def test_rejects_weak_or_missing_key(client, monkeypatch):
    monkeypatch.setenv("CURRENT_API_KEY", "weak")
    async with client as c:
        assert (await c.get("/v1/feeds", headers={"x-api-key": "weak"})).status_code == 503
    monkeypatch.setenv("CURRENT_API_KEY", KEY)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
        response = await c.get("/v1/feeds")
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "ApiKey"
        assert (await c.get("/v1/feeds", headers={"x-api-key": "wrong"})).status_code == 401
        assert (await c.get("/v1/feeds", headers={"x-api-key": KEY})).status_code == 200

@pytest.mark.asyncio
async def test_process_limit_and_health_bypass(monkeypatch):
    monkeypatch.setenv("CURRENT_API_KEY", KEY)
    monkeypatch.setattr(access, "api_limiter", AccessControl(limit=2, window_seconds=60))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
        for _ in range(2):
            assert (await c.get("/v1/feeds", headers={"x-api-key": KEY})).status_code == 200
        response = await c.get("/v1/feeds", headers={"x-api-key": KEY})
        assert response.status_code == 429
        assert response.headers["retry-after"] == "60"
        assert (await c.get("/healthz")).status_code == 200

@pytest.mark.asyncio
async def test_limiter_rolls_window(monkeypatch):
    clock = [100.0]
    monkeypatch.setattr(access.time, "monotonic", lambda: clock[0])
    limiter = AccessControl(limit=1, window_seconds=60)
    assert await limiter.allow()
    assert not await limiter.allow()
    clock[0] += 60
    assert await limiter.allow()


@pytest.mark.asyncio
async def test_authenticated_api_responses_are_not_cacheable(client, monkeypatch):
    monkeypatch.setenv("CURRENT_API_KEY", KEY)
    monkeypatch.setenv("CURRENT_FEEDS_JSON", "{}")
    monkeypatch.setattr(access, "api_limiter", AccessControl(limit=2, window_seconds=60))
    async with client as c:
        responses = [
            await c.get("/v1/feeds", headers={"x-api-key": KEY}),
            await c.get("/v1/feeds", headers={"x-api-key": "wrong"}),
            await c.get("/v1/feeds", headers={"x-api-key": KEY}),
            await c.get("/v1/feeds", headers={"x-api-key": KEY}),
        ]
        assert [response.status_code for response in responses] == [200, 401, 200, 429]
        for response in responses:
            assert response.headers["cache-control"] == "no-store"
            assert response.headers["x-content-type-options"] == "nosniff"
        assert (await c.get("/healthz")).status_code == 200


@pytest.mark.asyncio
async def test_unconfigured_api_response_is_not_cacheable(client, monkeypatch):
    monkeypatch.delenv("CURRENT_API_KEY", raising=False)
    async with client as c:
        response = await c.get("/v1/feeds")
        assert response.status_code == 503
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"
