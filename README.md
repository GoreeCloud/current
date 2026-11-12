# GoreeCloud Current

RSS and weather backend for the GoreeCloud ecosystem.

**Status:** Early development. Source has been committed; deployment, end-to-end network testing, and production hardening are not yet verified.

## API

- `GET /healthz` — process health
- `GET /v1/weather?latitude=40.7&longitude=-74` — current conditions and configurable 1–7 day forecast from Open-Meteo
- `GET /v1/feeds` — configured RSS/Atom feed names
- `GET /v1/feeds/{feed_name}` — up to 30 parsed entries from an operator-configured RSS/Atom feed

Optional query parameters for weather: `days` (1–7, default 5) and `temperature_unit` (`celsius` or `fahrenheit`). Invalid upstream weather payloads return HTTP 502.

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

## Interim API access controls

Versioned endpoints require a minimum 32-character `CURRENT_API_KEY` configured on the server, supplied via `X-API-Key`. Wrong or missing credentials return 401. A conservative process-local 60-request-per-60-second **global** limit returns 429 with `Retry-After`; it is **not** a distributed or per-user quota and can be bypassed across multiple workers. Treat the shared API key as a secret, use TLS at a trusted gateway, and avoid passing it in URLs. This is not yet GoreeCloud Identity integration, OAuth, user-scoped authorization, audit logging, or sufficient public exposure hardening.

## Security and privacy

The RSS API does not accept arbitrary URLs from callers. Sources are configured by the operator through `CURRENT_FEEDS_JSON`; use only sources you trust. HTTPS and no redirects are enforced. **RSS fetching is disabled by default** and returns HTTP 503. Additionally configure `CURRENT_FEED_ALLOWED_HOSTS` as a comma-separated list of exact DNS hostnames (for example, `example.org,feeds.example.net`). RSS requests fail closed unless their configured hostname is in that allowlist. This is defense-in-depth, **not** protection against DNS rebinding or a substitute for IP-level network controls. Set `CURRENT_FEED_EGRESS_GUARDED=1` only after independently verifying enforced outbound network isolation; this flag is an operator attestation, not an implemented firewall. Outbound response size is capped at 1 MiB and XML external entities are rejected. **HTTPS validation alone does not prevent DNS rebinding or private-network SSRF**: run this service behind an outbound network firewall/proxy that blocks internal, private, loopback, link-local, and metadata destinations. Do not expose it publicly until this and other deployment controls are in place.

Weather requests send the caller's coordinates to Open-Meteo. Do not submit sensitive precise locations without consent. Weather responses now use a 120-second, 128-entry, in-memory bounded cache with in-flight request coalescing. The cache stores exact coordinates in process memory only until expiry or eviction; it is not a durable history and is not shared across processes. Identity integration, distributed per-client quotas, provider attribution review, monitoring, and egress protections are still required before production use.

## Cache limits and assumptions

A cache reduces repeated upstream lookups but is not an API rate limiter or abuse defense. There are no distributed quotas or persistent cache controls. During high request volumes, different locations may still cause many upstream calls. Do not expose the service publicly without independent access controls and network policies.

## GoreeCloud integration

GoreeCloud Mesh coordinates API integration, GoreeShield governs location/privacy consent, Wardveil governs cybersecurity controls, and GoreeCloud UI governs frontend presentation. This repository implements a backend only.

## License

License selection and third-party notices remain to be reviewed; do not assume an open-source license is granted merely because this repository is public.
