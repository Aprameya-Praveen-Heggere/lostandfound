# V2 API

All endpoints remain under `/api/v1`; OpenAPI is `/api/docs`.

- Matching: `POST /matching/lost-reports/{id}/recompute`, `GET /matching/lost-reports/{id}`, `GET /matching/lost-reports/{id}/status`.
- Preferences/delivery: `GET|PUT /notifications/preferences`, `GET /admin/notification-deliveries`.
- Institution: `GET|PUT /institution/settings`, `POST|PATCH /institution/categories`, `POST|PATCH /institution/locations`, `GET|PUT /institution/oidc`, `GET|POST|PATCH /institution/providers`, `GET /institution/analytics`.
- SSO: `GET /sso/{institution_id}/login`, `GET /sso/callback`.
- Claims: `POST /claims/{id}/verification-request`, `POST /claims/{id}/handover-schedule` plus V1 lifecycle routes.
- Archival: `GET|PUT /archival/policy`, `GET /archival/preview`, `POST /archival/execute`, `POST /archival/{id}/restore`.
- Platform: `POST|PATCH /platform/institutions`, `PATCH /platform/institutions/{id}/users/{id}/role`, `GET /platform/analytics`, `GET /platform/providers/health`.

Institution and platform endpoints enforce role dependencies. Pagination is applied to delivery logs and existing found-item search. Provider credentials are never accepted in provider configuration payloads.
