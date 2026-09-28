# Security

Passwords use Argon2id through `pwdlib`; signed access tokens expire. Backend dependencies enforce user, officer, and administrator roles. Queries enforce institution boundaries, while claim evidence and attachments require authentication. Uploads accept verified JPEG/PNG/WebP signatures, cap size, discard client paths, and use random server filenames. ORM parameters prevent SQL injection. Login and registration have an in-process rate limit; security headers, bounded validation, audit trails, and restricted CORS are enabled.

Known MVP limitations: browser tokens use local storage rather than same-site HTTP-only cookies; the rate limiter is per process; token logout is client-side and has no revocation list; malware scanning and TLS termination belong to deployment infrastructure. Production should move tokens to secure cookies, use a shared limiter, rotate secrets, add upload malware scanning, and disable demo seeding.
