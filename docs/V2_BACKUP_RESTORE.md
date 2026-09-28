# V2 Backup and Restore

Database backup:

```bash
docker compose exec -T db pg_dump -U findora -d findora -Fc -f /tmp/findora.dump
docker cp lostandfound-db-1:/tmp/findora.dump backups/findora.dump
```

Back up the `findora_uploads` volume separately with infrastructure snapshot tooling; database attachment metadata and stored filenames must stay paired with files.

Restore to an empty database, then migrate:

```bash
docker compose exec db createdb -U findora findora_restore
docker cp backups/findora.dump lostandfound-db-1:/tmp/findora.dump
docker compose exec db pg_restore -U findora -d findora_restore /tmp/findora.dump
DATABASE_URL=postgresql+psycopg://.../findora_restore alembic upgrade head
```

On 2026-09-28, the pre-V2 dump was restored to a disposable PostgreSQL database, migrated through `0003_v2_workflow`, and verified with 4 users, 1 institution, and 5 found items before the disposable database was removed. The active existing-data database was subsequently migrated through `0005_notification_channels`, while a fresh database was independently migrated to the same head. Database restore is therefore tested; attachment-volume restore was documented but not exercised.
