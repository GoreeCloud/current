# GoreeCloud Current

RSS and weather backend for the GoreeCloud ecosystem.

**Status:** Early development. Source has been committed; deployment, end-to-end network testing, and production hardening are not yet verified.

## API

- `GET /healthz` — process health (does not imply configuration readiness)
- `GET /readyz` — local API-key and feed-registry configuration readiness; returns 503 when misconfigured, without echoing secrets or feed URLs. When guarded RSS fetching is configured and nonempty, also checks the exact-host allowlist locally. Does not test external providers, network egress enforcement, or production safety.
- `GET /v1/weather?latitude=40.7&longitude=-74` — current conditions and configurable 1–7 day forecast from Open-Meteo
- `GET /v1/feeds` — configured RSS/Atom feed names
- `GET /v1/feeds/{feed_name}` — up to 30 parsed entries from an operator-configured RSS/Atom feed; Atom article navigation prefers safe `rel=alternate` links rather than self/edit/enclosure relations; IP-literal and explicitly local article destinations are suppressed

Optional query parameters for weather: `days` (1–7, default 5) and `temperature_unit` (`celsius` or `fahrenheit`). Malformed weather upstream payloads (including missing or nonnumeric temperature and invalid daily dates) return HTTP 502 and are not cached.

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
# Generate a random 32+ character secret; never commit it.
export CURRENT_API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export CURRENT_FEEDS_JSON='{"example":"https://example.org/feed.xml"}'
uvicorn current.main:app --host 127.0.0.1 --port 8000
pytest -q
```

OpenAPI documentation is **disabled by default** because the interim API-key middleware does not protect `/docs`, `/redoc`, or `/openapi.json`. For local-only development, set `CURRENT_ENABLE_API_DOCS=1` before starting Uvicorn, then use `http://127.0.0.1:8000/docs`. Do not enable these endpoints on a public or shared deployment without separate gateway access controls. API calls to `/v1/*` must include `X-API-Key: <CURRENT_API_KEY>`; without a configured 32+ character key they fail closed with 503. `/healthz` remains unauthenticated.

## Container exposure defaults

The default container command now binds Uvicorn to **127.0.0.1 inside the container**. Publishing host ports with `docker run -p` does not make that loopback-only process reachable through the usual bridged container interface. `EXPOSE 8000` is Docker metadata, not an authorization to publish a port. This is an intentional safe development default, **not** a deployment-ready ingress design or outbound firewall.

Any non-loopback bind requires an explicit operator command override, a trusted TLS and GoreeCloud Identity gateway, separately enforced outbound network isolation, and a verified deployment acceptance plan. The application still lacks distributed rate limits, SSRF-safe egress, and production network testing. Do not use `0.0.0.0` merely to make the container reachable without those controls.

## Interim API access controls

Versioned endpoints require a 32–512-byte UTF-8 `CURRENT_API_KEY` configured on the server, supplied via `X-API-Key`. Wrong, missing, or duplicate `X-API-Key` header fields return 401. A conservative process-local 60-request-per-60-second **global** limit returns 429 with `Retry-After`; it is **not** a distributed or per-user quota and can be bypassed across multiple workers. Treat the shared API key as a secret, use TLS at a trusted gateway, and avoid passing it in URLs. This is not yet GoreeCloud Identity integration, OAuth, user-scoped authorization, audit logging, or sufficient public exposure hardening.

## Security and privacy

The RSS API does not accept arbitrary URLs from callers. Sources are configured by the operator through `CURRENT_FEEDS_JSON`; use only sources you trust. HTTPS and no redirects are enforced. **RSS fetching is disabled by default** and returns HTTP 503. Additionally configure `CURRENT_FEED_ALLOWED_HOSTS` as a comma-separated list of exact DNS hostnames (for example, `example.org,feeds.example.net`). RSS requests fail closed unless their configured hostname is in that allowlist. The hostname allowlist is bounded to 32 syntactically valid DNS names (4 KiB of configuration); malformed, empty, IP-literal and legacy numeric IPv4-style entries fail closed. The operator feed registry rejects the same ambiguous numeric host forms. This is defense-in-depth, **not** protection against DNS rebinding or a substitute for IP-level network controls. Set `CURRENT_FEED_EGRESS_GUARDED=1` only after independently verifying enforced outbound network isolation; this flag is an operator attestation, not an implemented firewall. Outbound response size is capped at 1 MiB; XML external entities are rejected, and parsed feeds exceeding 4,096 XML nodes or 32 nesting levels fail with 502. These parser bounds do not replace upstream network controls. **HTTPS validation alone does not prevent DNS rebinding or private-network SSRF**: run this service behind an outbound network firewall/proxy that blocks internal, private, loopback, link-local, and metadata destinations. Do not expose it publicly until this and other deployment controls are in place.

Weather requests send the caller's coordinates to Open-Meteo. Do not submit sensitive precise locations without consent. Weather responses now use a 120-second, 128-entry, in-memory bounded cache with in-flight request coalescing. The cache holds exact coordinates in process memory, with TTL eligibility and bounded eviction. Expired entries are now purged on subsequent cache activity, even when a different location is requested; an idle process may retain expired entries until activity resumes or it exits. It is not a durable history and is not shared across processes. Identity integration, distributed per-client quotas, provider attribution review, monitoring, and egress protections are still required before production use.

## Cache limits and assumptions

A cache reduces repeated upstream lookups but is not an API rate limiter or abuse defense. There are no distributed quotas or persistent cache controls. During high request volumes, different locations may still cause many upstream calls. Do not expose the service publicly without independent access controls and network policies.

## GoreeCloud integration

GoreeCloud Mesh coordinates API integration, GoreeShield governs location/privacy consent, Wardveil governs cybersecurity controls, and GoreeCloud UI governs frontend presentation. This repository implements a backend only.

## License

The GoreeCloud Current first-party source is licensed under the MIT License in [LICENSE](LICENSE). Third-party dependencies retain their own licenses and notices; the repository license does not override those obligations. This is a development preview, not proof of license compliance for a future bundled deployment.
