# V2 Security

V1 Argon2id passwords, expiring signed tokens, rate limits, validation, ORM parameters, CORS, upload signatures/limits, random filenames, private downloads, audit records, and safe errors remain.

V2 adds inactive-institution denial, tenant-owned taxonomy, OIDC state/nonce/audience/issuer/email-verification checks, user-only role assignment for new SSO identities, environment-referenced provider secrets, private embedding ownership, provider failure isolation, bounded retries, and archive authorization. Email previews contain no ownership evidence. Image providers explicitly exclude face recognition. AI never makes claim decisions.

Known limitation: browser tokens remain in local storage rather than HTTP-only cookies. Production should terminate TLS, rotate secrets, restrict CORS, use a shared edge rate limiter, and run a dedicated worker process if traffic requires it.
