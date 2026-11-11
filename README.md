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
export CURRENT_FEEDS_JSON='{"example":"https://example.org/feed.xml"}'
uvicorn current.main:app --host 127.0.0.1 --port 8000
pytest -q
```

OpenAPI docs: `http://127.0.0.1:8000/docs`.

## Security and privacy

The RSS API does not accept arbitrary URLs from callers. Sources are configured by the operator through `CURRENT_FEEDS_JSON`; use only sources you trust. HTTPS and no redirects are enforced. **RSS fetching is disabled by default** and returns HTTP 503. Set `CURRENT_FEED_EGRESS_GUARDED=1` only after independently verifying enforced outbound network isolation; this flag is an operator attestation, not an implemented firewall. Outbound response size is capped at 1 MiB and XML external entities are rejected. **HTTPS validation alone does not prevent DNS rebinding or private-network SSRF**: run this service behind an outbound network firewall/proxy that blocks internal, private, loopback, link-local, and metadata destinations. Do not expose it publicly until this and other deployment controls are in place.

Weather requests send the caller's coordinates to Open-Meteo. Do not submit sensitive precise locations without consent. Weather responses now use a 120-second, 128-entry, in-memory bounded cache with in-flight request coalescing. The cache stores exact coordinates in process memory only until expiry or eviction; it is not a durable history and is not shared across processes. Authentication, external quotas, provider attribution review, monitoring, and egress protections are still required before production use.

## Cache limits and assumptions

A cache reduces repeated upstream lookups but is not an API rate limiter or abuse defense. There are no distributed quotas or persistent cache controls. During high request volumes, different locations may still cause many upstream calls. Do not expose the service publicly without independent access controls and network policies.

## GoreeCloud integration

GoreeCloud Mesh coordinates API integration, GoreeShield governs location/privacy consent, Wardveil governs cybersecurity controls, and GoreeCloud UI governs frontend presentation. This repository implements a backend only.

## License

License selection and third-party notices remain to be reviewed; do not assume an open-source license is granted merely because this repository is public.
