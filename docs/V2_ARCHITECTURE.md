# V2 Architecture

Findora remains a modular monolith. API dependencies establish an authenticated institution context before repositories query tenant-owned rows. Critical state and audit records share database transactions. Non-critical matching and email work is represented by durable `background_jobs`; the in-process worker leases pending work, records bounded attempts, and isolates provider failure.

Matching applies institution/category/open-status hard filters, then structured scoring, local or configured text embeddings, and optional private-image embeddings. Results and explanations are persisted. Local providers make the system fully runnable offline; provider protocols permit controlled replacements.

Provider boundaries cover text/image embeddings, private storage, in-app/SMTP notification, and OIDC identity. The registry uses explicit imports and compatibility metadata; no arbitrary code loading exists. PostgreSQL remains authoritative, Nginx routes the React client and API, and Alembic owns schema evolution.
