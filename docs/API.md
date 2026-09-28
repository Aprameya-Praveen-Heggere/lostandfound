# API

All product endpoints use `/api/v1`; interactive OpenAPI is `/api/docs`. Authenticate with `Authorization: Bearer <token>`. Errors consistently return `{"detail":"message"}` (validation errors use FastAPI's structured detail list).

Groups include `/auth/register|login|logout|me`, `/categories`, `/locations`, `/lost-reports`, `/found-items`, `/search/found-items`, `/claims`, `/handovers`, `/notifications`, `/admin/analytics`, `/admin/audit-logs`, `/admin/users`, `/health`, `/ready`, and `/extensions`.

Example login:

```http
POST /api/v1/auth/login
Content-Type: application/json

{"email":"student@findora.edu","password":"Findora123!"}
```

Search requires `category_id`; optional `q`, `color`, `location`, `date_lost`, `sort`, `page`, and `page_size` refine or order only within that category. Photos are uploaded as multipart data to `/found-items/{id}/attachments` or `/lost-reports/{id}/attachments` and retrieved through authenticated `/attachments/{id}`.
