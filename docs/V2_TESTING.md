# V2 Testing

V2 adds tests for semantic relevance, hard category/status/date filters, provider fallback, private image similarity, non-automatic approval, preference suppression, OIDC state/nonce tampering, tenant settings/taxonomy, secret rejection, platform authorization/metrics, advanced analytics, repeatable archival restoration, and cross-tenant officer denial.

Run:

```bash
cd backend
../.venv/bin/pytest -m "not live"
LIVE_BASE_URL=http://localhost:8080/api/v1 ../.venv/bin/pytest -m live
cd ../frontend && npm run build
```

Migration verification must cover both a fresh database and a V1 backup upgraded to head. Provider failure tests must not require external services. See `TESTING.md` for the V1 baseline and detailed limitations.

Latest verified result (2026-09-28): 47 isolated tests passed, 3 live PostgreSQL tests passed, backend coverage was 90%, frontend lint/build passed, and fresh plus existing database migrations reached `0005_notification_channels`.
