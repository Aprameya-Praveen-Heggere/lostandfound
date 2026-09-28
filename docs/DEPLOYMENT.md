# Deployment

Configure `.env` from `.env.example`; use a high-entropy secret and database password. `docker compose up --build` starts PostgreSQL, waits for readiness, applies migrations, seeds data only when `ENVIRONMENT=development` and the database is empty, starts the API as a non-root user, then starts Nginx. Named volumes `findora_db` and `findora_uploads` persist state.

For backups, run `pg_dump` against the database and separately snapshot the upload volume. Restore the database with `pg_restore` and restore files with their original generated names. Test restores regularly. Terminate TLS at a trusted reverse proxy in production, set the exact HTTPS origin in `CORS_ORIGINS`, disable demo seeding, and supply secrets through the deployment platform rather than source files.
