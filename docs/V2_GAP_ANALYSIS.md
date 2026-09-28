# V2 Gap Analysis

## Existing MVP

V1 provided FastAPI/SQLAlchemy/PostgreSQL, React/TypeScript/Tailwind, Argon2/JWT authentication, direct institution ownership on operational records, user/officer/admin roles, lost/found reports, category-hard-filtered deterministic search, claims, decisions, handovers, in-app notifications, audit logs, local private storage, basic analytics, Alembic, Docker Compose, and 33 automated tests. Storage, notification, event, and controlled extension boundaries already existed.

## Gaps closed by V2

- Hybrid structured plus semantic matching, persisted explanations/confidence, provider failure fallback, optional image signal, and durable recomputation jobs.
- Tenant-owned categories, memberships, settings, OIDC configuration, retention, providers, and platform-super-admin authority.
- SMTP adapter, preferences, delivery attempts/status, bounded durable jobs, additional-verification and scheduled-handover events.
- Institution date-filtered analytics, platform metrics, archival preview/execute/restore, provider health, and tested backup/restore.
- User match/preference views plus institution and platform administration consoles.

## Database and API changes

Migrations `0002_findora_v2`, `0003_v2_workflow`, `0004_handover_archival`, and `0005_notification_channels` add V2 tables/columns and backfill tenant taxonomy, memberships, settings, retention, one platform administrator, reversible handover archival, and independent channel visibility without removing V1 data. `/api/v1` remains stable; new matching, institution, platform, SSO, preference, provider, analytics, and archival groups are additive.

## Security and compatibility

Tenant IDs remain mandatory at query boundaries. Categories are now authenticated and tenant-scoped. Images remain behind authenticated attachment routes. Provider secrets are environment references, never API responses. Existing password login, reports, claims, decisions, and handovers retain their URLs and semantics. The category endpoint now requires authentication, which matches all product flows but is an intentional tightening for tenant privacy.

## Deployment changes

No new distributed service is required. A database-backed bounded-retry worker runs within the modular monolith. Optional SMTP and per-institution OIDC require environment configuration. Back up the database and attachment volume before migration.
