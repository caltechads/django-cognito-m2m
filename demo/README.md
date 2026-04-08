# Demo API Authentication

This demo protects its DRF endpoints with [`django-cognito-m2m`](https://pypi.org/project/django-cognito-m2m/).

Protected endpoints:

- `/api/authors/`
- `/api/authors/<id>/`
- `/api/books/`
- `/api/books/<id>/`

## Runtime Configuration

Set these environment variables before calling the protected API with a real Cognito token:

```bash
export COGNITO_M2M_REGION=us-west-2
export COGNITO_M2M_USER_POOL_ID=us-west-2_AbCdEfGhI
export COGNITO_M2M_AUDIENCE=your-api-audience
export COGNITO_M2M_TRACK_CLIENT_ACTIVITY=1
```

`COGNITO_M2M_AUDIENCE` is optional. Leave it unset if your validator configuration does not require an audience check.
`COGNITO_M2M_TRACK_CLIENT_ACTIVITY` is optional. Set it to `1` if you want the demo to record `client_id`, `first_seen_at`, and `last_seen_at` for authenticated clients.

If you enable client activity tracking, make sure the project includes `"django_cognito_m2m"` in `INSTALLED_APPS` and run:

```bash
./.venv/bin/python manage.py migrate
```

## Scope Contract

The demo uses a split read/write scope model across both resources:

- `catalog/read`: required for `GET`, `HEAD`, and `OPTIONS`
- `catalog/write`: required for `POST`, `PUT`, `PATCH`, and `DELETE`

Successful authenticated requests expose:

- `request.auth` as the `ServicePrincipal`
- `request.service_principal` as the same principal
- `request.user` as `AnonymousUser`

## Error Behavior

- Missing bearer token: `401 Unauthorized`
- Invalid bearer token: `401 Unauthorized`
- Valid token without the required scope: `403 Forbidden`

## Running The Demo

Start the Django server:

```bash
./.venv/bin/python manage.py runserver
```

Call a read endpoint with a valid bearer token:

```bash
curl \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  http://127.0.0.1:8000/api/authors/
```

Create a book with a token that has `catalog/write`:

```bash
curl \
  -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "The Fifth Season",
    "authors": [{"author_id": 1, "order": 1}]
  }' \
  http://127.0.0.1:8000/api/books/
```

## Smoke Script

The smoke test now expects an auth token for every run:

```bash
./.venv/bin/python scripts/api_smoke.py \
  --auth-token "$ACCESS_TOKEN" \
  --cleanup
```

Use a token with both `catalog/read` and `catalog/write` if you want the full create, fetch, update, and delete scenario to succeed.
