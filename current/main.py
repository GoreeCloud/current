"""GoreeCloud Current: RSS feeds and weather, with bounded outbound requests."""
import os
import json
import math
import ipaddress
import itertools
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlsplit

import httpx
from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from current.cache import BoundedTTLCache, CacheBusyError
from current.access import enforce_api_access
from fastapi import FastAPI, HTTPException, Query

# Documentation is opt-in because /docs and /openapi.json are not API-key guarded.
_DOCS_ENABLED = os.getenv("CURRENT_ENABLE_API_DOCS") == "1"
app = FastAPI(
    title="GoreeCloud Current",
    version="0.1.0",
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
)
app.middleware("http")(enforce_api_access)
MAX_RESPONSE_BYTES = 1_048_576
TIMEOUT = httpx.Timeout(8.0, connect=3.0)
WEATHER_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
weather_cache = BoundedTTLCache(ttl_seconds=120, max_entries=128, max_value_bytes=MAX_RESPONSE_BYTES)


async def get_bounded(url: str, *, params: dict | None = None) -> bytes:
    """Limit memory, time and redirects for outbound HTTP calls."""
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False, trust_env=False) as client:
        try:
            async with client.stream("GET", url, params=params, headers={"User-Agent": "GoreeCloud-Current/0.1"}) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    raise HTTPException(502, "Upstream redirects are disabled")
                response.raise_for_status()
                length = response.headers.get("content-length")
                if length is not None:
                    try:
                        declared = int(length)
                    except ValueError as exc:
                        raise HTTPException(502, "Invalid upstream content length") from exc
                    if declared < 0 or declared > MAX_RESPONSE_BYTES:
                        raise HTTPException(502, "Upstream response too large")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise HTTPException(502, "Upstream response too large")
                return bytes(body)
        except httpx.HTTPError as exc:
            raise HTTPException(502, "Upstream service unavailable") from exc


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "GoreeCloud Current"}


@app.get("/readyz")
async def readyz():
    """Local configuration readiness, not upstream connectivity or egress proof."""
    key = os.getenv("CURRENT_API_KEY", "")
    if len(key) < 32 or key != key.strip():
        raise HTTPException(503, "Current API authentication is not configured")
    try:
        configured_feeds()
    except HTTPException as exc:
        raise HTTPException(503, "Current feed configuration is invalid") from exc
    return {"status": "ready", "service": "GoreeCloud Current"}


@app.get("/v1/weather")
async def weather(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    days: int = Query(default=5, ge=1, le=7),
    temperature_unit: str = Query(default="celsius", pattern="^(celsius|fahrenheit)$"),
):
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise HTTPException(422, "Coordinates must be finite")
    # No persistent location history; cache entries expire and are bounded.
    key = (latitude, longitude, days, temperature_unit)

    def decode_weather(data: bytes) -> dict:
        try:
            # Python accepts NaN/Infinity by default, but they are not valid JSON
            # numbers and cannot be safely serialized in an API response.
            def reject_nonfinite(value: str):
                raise ValueError("Non-finite upstream JSON number")

            result = json.loads(data, parse_constant=reject_nonfinite)
        except (ValueError, UnicodeDecodeError, RecursionError) as exc:
            raise HTTPException(502, "Invalid weather upstream response") from exc
        if (not isinstance(result, dict)
                or not isinstance(result.get("current"), dict)
                or not isinstance(result.get("daily"), dict)):
            raise HTTPException(502, "Unexpected weather upstream schema")
        return result

    async def fetch_weather() -> bytes:
        data = await get_bounded(WEATHER_ENDPOINT, params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "timezone": "auto",
            "forecast_days": days,
            "temperature_unit": temperature_unit,
        })
        # Validate before inserting into cache; never cache malformed provider data.
        decode_weather(data)
        return data

    try:
        data = await weather_cache.get_or_fetch(key, fetch_weather)
    except CacheBusyError as exc:
        raise HTTPException(503, "Weather provider capacity exhausted") from exc
    return decode_weather(data)


def configured_feeds() -> dict[str, str]:
    """Operator-managed feed registry; never fetch arbitrary user-provided URLs."""
    raw = os.getenv("CURRENT_FEEDS_JSON", "{}")
    try:
        feeds = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(503, "Feed registry misconfigured") from exc
    if not isinstance(feeds, dict) or len(feeds) > 32:
        raise HTTPException(503, "Feed registry misconfigured")
    for name, url in feeds.items():
        if (not isinstance(name, str) or not name or len(name) > 64
                or not isinstance(url, str) or not url or len(url) > 2048
                or any(ord(char) < 33 or ord(char) == 127 for char in url)):
            raise HTTPException(503, "Feed registry misconfigured")
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError as exc:
            raise HTTPException(503, "Invalid feed registry URL") from exc
        hostname = parsed.hostname or ""
        if (parsed.scheme != "https" or not hostname or parsed.username or parsed.password
                or port not in (None, 443) or parsed.fragment
                or not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", hostname)
                or "." not in hostname or hostname.endswith(".")
                or not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label) for label in hostname.split("."))
                or hostname.lower().endswith((".local", ".internal", ".localhost"))
                or hostname.lower() == "localhost"):
            raise HTTPException(503, "Feed registry requires public HTTPS hostnames")
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise HTTPException(503, "Feed registry rejects IP literals")
    return feeds


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(node: ET.Element, name: str) -> str:
    for child in node:
        if local_name(child.tag) == name:
            return (child.text or "").strip()[:2000]
    return ""


def safe_article_link(raw: str) -> str:
    """Expose only bounded, absolute HTTP(S) article URLs from untrusted XML."""
    if not isinstance(raw, str):
        return ""
    raw = raw.strip()
    if not raw or len(raw) > 2048 or any(ord(c) < 32 or ord(c) == 127 for c in raw):
        return ""
    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return ""
    if (parsed.scheme not in ("https", "http") or not hostname
            or parsed.username is not None or parsed.password is not None
            or port is not None and not (1 <= port <= 65535)
            or not parsed.netloc or any(c.isspace() for c in raw)):
        return ""
    return raw


def parse_feed(body: bytes) -> list[dict]:
    if not isinstance(body, bytes) or len(body) > MAX_RESPONSE_BYTES:
        raise HTTPException(502, "Invalid RSS or Atom XML")
    try:
        root = SafeET.fromstring(body)
    except (ET.ParseError, ValueError, DefusedXmlException) as exc:
        raise HTTPException(502, "Invalid RSS or Atom XML") from exc
    if local_name(root.tag) not in ("rss", "feed", "RDF"):
        raise HTTPException(502, "Unsupported feed format")
    items = itertools.islice((node for node in root.iter() if local_name(node.tag) in ("item", "entry")), 30)
    return [
        {
            "title": child_text(node, "title"),
            "link": safe_article_link(child_text(node, "link") or next(
                (child.attrib.get("href", "") for child in node if local_name(child.tag) == "link"), ""
            )),
            "published": child_text(node, "pubDate") or child_text(node, "published") or child_text(node, "updated"),
            "summary": child_text(node, "description") or child_text(node, "summary"),
        }
        for node in items
    ]


@app.get("/v1/feeds")
async def list_feeds():
    return {"feeds": sorted(configured_feeds())}


@app.get("/v1/feeds/{feed_name}")
async def read_feed(feed_name: str):
    feeds = configured_feeds()
    if feed_name not in feeds:
        raise HTTPException(404, "Unknown feed")
    # Fail closed: hostname validation does not prevent DNS rebinding.
    if os.getenv("CURRENT_FEED_EGRESS_GUARDED") != "1":
        raise HTTPException(503, "RSS fetching disabled until guarded network egress is configured")
    # Exact-host allowlist is defense-in-depth, NOT DNS/IP egress enforcement.
    raw_hosts = os.getenv("CURRENT_FEED_ALLOWED_HOSTS", "")
    allowed = {host.strip().lower() for host in raw_hosts.split(",") if host.strip()}
    if not allowed or any(not re.fullmatch(r"[a-z0-9.-]{1,253}", host) for host in allowed):
        raise HTTPException(503, "RSS hostname allowlist not configured")
    hostname = urlsplit(feeds[feed_name]).hostname
    if hostname not in allowed:
        raise HTTPException(503, "RSS source not explicitly allowlisted")
    data = await get_bounded(feeds[feed_name])
    return {"feed": feed_name, "items": parse_feed(data), "retrieved_at": datetime.now(timezone.utc).isoformat()}
