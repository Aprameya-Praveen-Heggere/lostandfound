# Architecture

Findora is a modular monolith: one FastAPI process owns identity, reports, discovery, claims, handovers, notifications, audit, analytics, and controlled extensions. React is a separate browser client; PostgreSQL is the system of record; Nginx serves the built client and proxies `/api`.

Core state changes run in database transactions. Route dependencies authenticate and enforce roles; every business query additionally scopes records by `institution_id`. Services hold deterministic matching and audit behavior. Provider protocols isolate local file storage and in-app notification delivery from future S3/email adapters.

The controlled extension registry accepts explicitly imported `Extension` objects declaring identity, version, configuration, handlers, enabled state, and health. It never imports arbitrary code. Domain event names are `item.reported`, `item.found`, `claim.submitted`, `claim.approved`, `claim.rejected`, and `item.handover.completed`. Audit data is persisted in the same transaction; non-critical handlers may be dispatched in process.

Version 2 can add a transactional outbox table written alongside core state. A separate dispatcher would lease unsent rows and deliver idempotently, without changing domain services or introducing a distributed bus prematurely.
