# V2 Deployment

Run `docker compose up --build`. Migrations execute before API startup; development seed runs only with `ENVIRONMENT=development`.

Required core variables: `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS`, PostgreSQL variables, and upload path/limit. Optional email variables are `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, and `SMTP_USE_TLS`. Set institution `email_enabled` and user preferences as well. OIDC uses `OIDC_REDIRECT_BASE`; each database config points to a client-secret environment-variable name.

Before V2 migration, back up PostgreSQL and uploads. Apply `alembic upgrade head` from `backend/`. Verify `/api/v1/ready`, provider health, login, matching, and private attachment access. No Redis, Kubernetes, or distributed bus is required.

Unhandled exceptions and background-loop failures are emitted through Python's structured logging channel. Production deployments can attach an error-tracking logging handler without changing domain code; the default deployment does not send telemetry to an external vendor.
