# V2 Multi-Tenancy

Every institution-owned table carries `institution_id`. Authentication resolves the user and rejects inactive users or institutions. `owned()` returns 404 for cross-tenant object IDs to reduce enumeration. Search, matching, attachments, claims, audit, analytics, archives, taxonomy, locations, notifications, providers, and SSO configuration are tenant-scoped.

Roles are user, officer, institution admin, and platform super admin. Membership records preserve institution-role assignments while the direct user institution/role columns keep V1 compatibility. Institution admins cannot access platform routes. Platform admins create/activate institutions and see aggregate operational metrics; they do not bypass ownership-verification workflows.
