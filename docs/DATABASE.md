# Database

PostgreSQL entities are institutions, users (role included), categories, locations, lost reports, found items, attachments, claims, handovers, notifications, audit logs, and extension metadata. UUID-form string primary keys permit later database portability. Reports have human-readable unique references.

Foreign keys preserve relationships; unique constraints prevent duplicate claims and handovers; institution, owner, status, category, and audit fields are indexed. Every operational record carries institution ownership. Alembic migration `0001_initial` creates the schema from the authoritative SQLAlchemy metadata. New schema changes must receive new revisions; production must never use automatic startup table creation.
