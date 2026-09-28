# Testing

## Test layers

The suite is split with Pytest markers:

- `unit`: security primitives, deterministic matching, schema validation, extension dispatch, and local-storage safety.
- `integration`: FastAPI routes with a fresh isolated SQLAlchemy database, real password hashing, authorization dependencies, transactions, audit records, notifications, and file persistence through an isolated test adapter.
- `live`: read-only smoke tests through Nginx against the running Docker/PostgreSQL deployment.

## Commands

From `backend/` after installing `requirements-dev.txt`:

```bash
pytest -m unit
pytest -m "integration and not live"
pytest -m "not live" --cov=app --cov-report=term-missing
LIVE_BASE_URL=http://localhost:8080/api/v1 pytest -m live
```

Validate the frontend independently:

```bash
cd frontend
npm run build
```

## Verified behavior

The automated suite covers:

- Argon2 password hashing, salting, verification, signed-token decoding, and tamper rejection.
- Institutional registration, login failures, duplicate accounts, logout response, authentication rate limiting, and security headers.
- Lost/found validation, creation, ownership edits, officer-only custody edits, report references, and future-date rejection.
- Strict category boundaries, relevance signals, score caps, location refinement, sorting inputs, and pagination.
- JPEG/PNG/WebP content-signature enforcement, invalid MIME rejection, authenticated download, and institution-private attachments.
- Claim creation, duplicate prevention, invalid transitions, officer role checks, rejection reasons, approval, handover, and recovered state.
- In-app notification creation/read state and ownership protection.
- Audit creation, administrator analytics, administrator access, role changes, and self-demotion protection.
- Cross-institution denial for reports, items, search results, attachments, notifications, and administrative operations.
- Extension registry enable/disable and handler dispatch behavior.
- Health, readiness, extension health, OpenAPI reachability, seed-data access, and production client compilation.

## Latest baseline

Recorded on 2026-09-28 after the V2 upgrade:

- Isolated backend unit/integration suite: **47 passed**, 3 live tests deselected.
- Live Docker/PostgreSQL suite: **3 passed**.
- Backend statement coverage: **90%** across the expanded V2 application.
- Frontend TypeScript lint/type-check and Vite production build: passed.
- Fresh Alembic upgrade: revision `0005_notification_channels` (head).
- Existing PostgreSQL data migrated from the V1/V2 baseline through revision `0005_notification_channels` without removing seeded or user records.
- A pre-V2 database dump was restored into a disposable PostgreSQL database and verified; see `V2_BACKUP_RESTORE.md`.
- Docker services: PostgreSQL, backend, and frontend healthy; readiness and OpenAPI (59 paths) reachable.

The warnings emitted under local Python 3.14 are upstream FastAPI/Starlette deprecation warnings for APIs planned to change in Python 3.16. The deployment image uses Python 3.12 and is not affected at runtime today.

## Remaining test limitations

- No browser automation suite currently drives the UI in Chromium/WebKit; the frontend is type-checked and production-built, while user workflows are exercised at the API layer.
- No sustained load, soak, chaos, attachment-volume restore, or malware-scanner test is included.
- SQLite provides fast isolated integration tests; live tests cover PostgreSQL health, authentication, authorization, search, matching, and platform visibility using seeded data while avoiding destructive mutations.
- SMTP failure/retry and OIDC callback behavior are tested with controlled providers. A real external mail server and institution identity provider still require environment-specific acceptance testing.
- The included storage adapter is private local-volume storage; the provider boundary is ready for a future S3-compatible adapter, but no cloud storage provider is bundled.
