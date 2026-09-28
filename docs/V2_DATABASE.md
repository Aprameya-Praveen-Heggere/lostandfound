# V2 Database

V2 reuses institutions, users, categories, locations, reports, items, attachments, claims, handovers, notifications, audit logs, and extension metadata.

Added entities: institution memberships/settings, identity-provider configs, item embeddings, matching results, notification preferences/deliveries, background jobs, retention policies, archive records, and extension-provider configs. Claims gain verification-request and handover-schedule timestamps. Reports/items gain reversible archive flags. Users gain platform-admin authority. Categories gain institution ownership and a composite institution/slug uniqueness rule.

Migration `0002_findora_v2` is additive and backfills existing records. `0003_v2_workflow` adds workflow fields and bootstraps one existing administrator as platform admin. `0004_handover_archival` adds reversible archival metadata to completed handovers. `0005_notification_channels` makes in-app visibility independent from email delivery. The later migrations are safe on fresh databases whose initial schema is generated from current metadata. Downgrades remove V2 structures, so a backup is mandatory before downgrade. No production data is automatically deleted.
