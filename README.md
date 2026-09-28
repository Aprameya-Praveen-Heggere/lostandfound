# Findora V2

Findora is a multi-institution lost-and-found platform covering report, hybrid semantic/image-assisted discovery, private ownership claims, human officer decisions, scheduled and completed handovers, notifications, analytics, and reversible archival. AI signals are advisory and are always hard-filtered by institution, category, availability, and date context.

## Run with Docker

Prerequisites: Docker Engine 24+ with Compose v2. Copy `.env.example` to `.env`, replace every placeholder (especially `SECRET_KEY` and database password), then run:

```bash
docker compose up --build
```

Open `http://localhost:8080`. API documentation is at `http://localhost:8080/api/docs`. Database and uploads use named persistent volumes. Migrations and development seed data run at backend startup and are idempotent.

V2 runs without external AI, SMTP, or OIDC services: local deterministic semantic/image providers remain available, email remains queued only when SMTP and institution email are enabled, and password login remains active when OIDC is absent. See `docs/V2_DEPLOYMENT.md` for provider variables.

## Development demo accounts

All use password `Findora123!` and exist only after running `python seed.py` or Docker startup:

- Student: `student@findora.edu`
- Officer: `officer@findora.edu`
- Administrator: `admin@findora.edu`

Never use these credentials or the Compose fallback secrets in production.

## Local development and tests

Backend (Python 3.12+): create a virtual environment, install `backend/requirements.txt`, then from `backend/` run `alembic upgrade head`, `python seed.py`, and `uvicorn app.main:app --reload`. The default local database is SQLite for convenience; Docker and production use PostgreSQL.

Frontend (Node 20+): from `frontend/`, run `npm install` then `npm run dev`. Vite proxies `/api` to the backend. Install `backend/requirements-dev.txt` for test coverage tooling. Run isolated tests with `cd backend && pytest -m 'not live'`; run deployment smoke tests with `LIVE_BASE_URL=http://localhost:8080/api/v1 pytest -m live`; and build the client with `npm run build`.

## Troubleshooting

- Check service state with `docker compose ps` and logs with `docker compose logs backend`.
- A registration email must match a seeded institution domain (`findora.edu` in demo data).
- To start over in development, `docker compose down -v` deletes database and upload volumes.
- If port 8080 is occupied, change the frontend port mapping in `docker-compose.yml`.

Architecture, API, security, database, deployment, testing, product requirements, and scope decisions are documented in [`docs/`](docs/). See [`docs/TESTING.md`](docs/TESTING.md) for the test matrix and reproducible commands.
