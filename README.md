# django-cognito-m2m

`django-cognito-m2m` is a reusable Django library for machine-to-machine OAuth bearer-token authentication and authorization using AWS Cognito access tokens.

It integrates with the existing [`m2m-cognito`](https://pypi.org/project/m2m-cognito/) Python library and treats that package as the source of truth for Cognito token validation. This package does not reimplement JWT verification. Instead, it provides Django and Django REST Framework integration around `m2m_cognito.CognitoAccessTokenValidator`.

The preferred long-term model is machine principal authentication:

- `request.auth` and `request.service_principal` are the canonical machine identity.
- `request.user` mapping exists to support staged migrations from legacy APIs that model clients as Django `User` rows.
- User mapping should be used carefully and intentionally.

## Why This Exists

Teams often want Cognito-backed machine authentication in Django, but they need more than token validation:

- DRF authentication classes and reusable permissions
- Plain Django middleware, decorators, and CBV mixins
- Clear 401 vs 403 error behavior
- Consistent request access helpers
- Safe migration from user-backed API clients to service principals

This package provides those pieces while delegating Cognito token verification to `m2m-cognito`.

## Relationship to `m2m-cognito`

`m2m-cognito` remains responsible for:

- fetching client-credentials tokens from Cognito
- validating Cognito JWT access tokens
- enforcing upstream token cryptography and Cognito-specific claim checks

`django-cognito-m2m` adds:

- Django and DRF request integration
- a canonical immutable service principal model
- scope and client-id authorization helpers
- optional Django user mapping and proxy-user compatibility
- API-friendly error responses

## Installation

Install the base package and the upstream validator dependency:

```bash
pip install m2m-cognito django-cognito-m2m
```

If you want DRF support, install the extra:

```bash
pip install m2m-cognito 'django-cognito-m2m[drf]'
```

If you enable built-in client activity tracking, also add the app to `INSTALLED_APPS` and run migrations:

```python
INSTALLED_APPS = [
    # ...
    "django_cognito_m2m",
]
```

```bash
python manage.py migrate
```

## Supported Stack

- Python 3.10+
- Django 4.2 through 5.x
- Django REST Framework 3.15+ when using the `drf` extra

## Configuration

Add the settings block below to your Django project:

```python
COGNITO_M2M = {
    "REGION": "us-west-2",
    "USER_POOL_ID": "us-west-2_AbCdEfGhI",

    "VALIDATOR_CLASS": None,
    "VALIDATOR_KWARGS": {},

    "ALLOWED_CLIENT_IDS": None,
    "AUDIENCE": None,

    "HEADER_NAME": "HTTP_AUTHORIZATION",
    "HEADER_PREFIX": "Bearer",

    "REQUEST_PRINCIPAL_ATTR": "service_principal",
    "REQUEST_AUTH_ATTR": "auth",

    "DEFAULT_SCOPE_MATCH": "all",

    "USER_MAPPING_ENABLED": False,
    "USER_MAPPING_STRATEGY": None,
    "USER_MAPPING_FIELD": None,
    "USER_MAPPING_CLAIM": None,
    "USER_MAPPING_CALLABLE": None,
    "USER_MAPPING_CLASS": None,

    "RETURN_USER_PROXY": False,
    "TRACK_CLIENT_ACTIVITY": False,
    "FAIL_ON_INVALID_BEARER": True,
    "JSON_ERROR_RESPONSES": True,
}
```

### Important settings

- `REGION` and `USER_POOL_ID` are required to construct the Cognito validator.
- `VALIDATOR_CLASS` lets you override the validator class with a dotted import path.
- `VALIDATOR_KWARGS` lets you pass additional constructor kwargs to the validator.
- `HEADER_NAME` and `HEADER_PREFIX` control bearer token extraction.
- `ALLOWED_CLIENT_IDS` acts as a default allowlist for permission and mixin layers.
- `TRACK_CLIENT_ACTIVITY` stores `client_id`, `first_seen_at`, and `last_seen_at` for authenticated machine clients.
- `FAIL_ON_INVALID_BEARER` controls whether plain Django middleware returns 401 immediately for invalid Bearer tokens.
- `JSON_ERROR_RESPONSES` controls whether plain Django errors return JSON or plain text.

## Client Activity Tracking

Enable built-in client activity tracking when you want a lightweight activity table for machine clients:

```python
COGNITO_M2M = {
    "TRACK_CLIENT_ACTIVITY": True,
}
```

When enabled:

- `django_cognito_m2m` must be present in `INSTALLED_APPS`
- `python manage.py migrate` must be run so the activity table exists
- one row is stored per `client_id`
- `first_seen_at` records the first authenticated request observed for that client
- `last_seen_at` is updated on each authenticated request

This feature is informational only. It does not store tokens, scopes, IP addresses, or request counters, and it should not be used as an authorization source of truth.

## Shared Principal Model

Every successful machine authentication resolves to `django_cognito_m2m.principal.ServicePrincipal`:

```python
from django_cognito_m2m.principal import ServicePrincipal

principal.client_id
principal.scopes
principal.claims
principal.raw_token
principal.has_scope("widgets/read")
principal.has_scopes("widgets/read", "widgets/admin", match="any")
principal.sub
principal.aud
principal.iss
principal.exp
```

This principal is immutable and is the canonical machine identity across DRF and plain Django integrations.

## DRF Quick Start

```python
from rest_framework.response import Response
from rest_framework.views import APIView

from django_cognito_m2m.drf.authentication import CognitoM2MAuthentication
from django_cognito_m2m.drf.permissions import HasCognitoScopes


class WidgetListView(APIView):
    authentication_classes = [CognitoM2MAuthentication]
    permission_classes = [HasCognitoScopes]
    required_scopes = {"widgets/read"}

    def get(self, request):
        principal = request.auth
        return Response(
            {
                "client_id": principal.client_id,
                "scopes": sorted(principal.scopes),
                "user": getattr(request.user, "username", None),
            }
        )
```

### DRF method-based scopes

```python
from rest_framework.response import Response
from rest_framework.views import APIView

from django_cognito_m2m.drf.authentication import CognitoM2MAuthentication
from django_cognito_m2m.drf.permissions import MethodScopePermission


class WidgetView(APIView):
    authentication_classes = [CognitoM2MAuthentication]
    permission_classes = [MethodScopePermission]
    scope_map = {
        "GET": {"widgets/read"},
        "POST": {"widgets/write"},
    }

    def get(self, request):
        return Response({"ok": True})

    def post(self, request):
        return Response({"ok": True})
```

### Available DRF permissions

- `HasCognitoScopes`
- `HasAllCognitoScopes`
- `HasAnyCognitoScope`
- `MethodScopePermission`
- `AllowedClientIdsPermission`

### DRF request contract

On successful machine authentication:

- `request.auth` is the `ServicePrincipal`
- `request.service_principal` is also attached for consistency
- `request.user` is one of:
  - `AnonymousUser` by default
  - a mapped Django user when mapping is enabled
  - a lightweight proxy user when `RETURN_USER_PROXY=True`

## Plain Django Quick Start

### Middleware

Add the middleware when you want machine principals attached automatically:

```python
MIDDLEWARE = [
    # ...
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_cognito_m2m.django.middleware.CognitoM2MMiddleware",
]
```

The middleware is permissive by default:

- no Authorization header: request continues untouched
- non-Bearer scheme: request continues untouched
- valid Bearer token: principal is attached
- invalid Bearer token:
  - returns 401 if `FAIL_ON_INVALID_BEARER=True`
  - otherwise continues without an attached principal

### Function views

```python
from django.http import JsonResponse

from django_cognito_m2m.django.decorators import require_scopes


@require_scopes("widgets/read")
def widget_view(request):
    principal = request.service_principal
    return JsonResponse(
        {
            "client_id": principal.client_id,
            "scopes": sorted(principal.scopes),
        }
    )
```

### Class-based views

```python
from django.http import JsonResponse
from django.views import View

from django_cognito_m2m.django.mixins import CognitoScopeRequiredMixin


class WidgetCBV(CognitoScopeRequiredMixin, View):
    required_scopes = {"widgets/read"}

    def get(self, request, *args, **kwargs):
        return JsonResponse({"ok": True})
```

### Available plain Django helpers

- decorators:
  - `require_authentication`
  - `require_scopes`
  - `require_any_scope`
  - `require_all_scopes`
  - `allow_client_ids`
- CBV mixins:
  - `CognitoAuthenticationRequiredMixin`
  - `CognitoScopeRequiredMixin`
  - `CognitoClientIdRequiredMixin`

## Authorization Patterns

### Simple required scopes

```python
required_scopes = {"widgets/read"}
```

### Any/all matching

```python
required_scopes = {"widgets/read", "widgets/admin"}
scope_match = "any"
```

### Method-based scopes

```python
scope_map = {
    "GET": {"widgets/read"},
    "POST": {"widgets/write"},
    "PUT": {"widgets/write"},
    "PATCH": {"widgets/write"},
    "DELETE": {"widgets/write"},
}
```

### Client allowlists

```python
allowed_client_ids = {"my-reporting-client", "sync-worker"}
```

## Staged Migration from Django User-Based API Auth

This package supports three practical modes.

### Mode A: machine principal only

Default behavior:

- `request.auth` and `request.service_principal` contain the machine principal
- `request.user` remains `AnonymousUser`
- no database lookup is required unless client activity tracking is enabled

This is the preferred long-term design.

### Mode B: machine principal plus mapped Django user

Use this when older business logic or permission code still expects `request.user`:

```python
COGNITO_M2M = {
    "USER_MAPPING_ENABLED": True,
    "USER_MAPPING_STRATEGY": "client_id_field",
    "USER_MAPPING_FIELD": "username",
}
```

With this configuration, a validated principal whose `client_id` is `reporting-client` can map to `User(username="reporting-client")`.

The machine identity still remains available on `request.auth` and `request.service_principal`.

### Mode C: proxy user compatibility

Use this when you need a user-like object without requiring a database row:

```python
COGNITO_M2M = {
    "RETURN_USER_PROXY": True,
}
```

The proxy user:

- has `is_authenticated = True`
- has `is_anonymous = False`
- exposes `username` and `client_id`
- keeps a back-reference to the `ServicePrincipal`
- does not pretend to be a real Django user row

## User Mapping Strategies

### Map by `client_id` to a user field

```python
COGNITO_M2M = {
    "USER_MAPPING_ENABLED": True,
    "USER_MAPPING_STRATEGY": "client_id_field",
    "USER_MAPPING_FIELD": "username",
}
```

### Map by claim value to a user field

```python
COGNITO_M2M = {
    "USER_MAPPING_ENABLED": True,
    "USER_MAPPING_STRATEGY": "claim_field",
    "USER_MAPPING_FIELD": "username",
    "USER_MAPPING_CLAIM": "sub",
}
```

### Map with a callable

```python
COGNITO_M2M = {
    "USER_MAPPING_ENABLED": True,
    "USER_MAPPING_STRATEGY": "callable",
    "USER_MAPPING_CALLABLE": "my_project.auth.map_service_principal_to_user",
}
```

### Map with a mapper class

```python
COGNITO_M2M = {
    "USER_MAPPING_ENABLED": True,
    "USER_MAPPING_STRATEGY": "class",
    "USER_MAPPING_CLASS": "my_project.auth.ServicePrincipalUserMapper",
}
```

### Mapping safety guarantees

- user mapping is optional
- mapping misses do not authenticate as the wrong user
- the principal remains available even when a user is mapped
- ambiguous or failing lookups raise `UserMappingError`

## Request Principal Access Patterns

Application code should treat the principal as the source of machine identity:

```python
principal = request.auth or request.service_principal
principal.client_id
principal.scopes
principal.has_scope("widgets/read")
```

You can also use the helper functions:

```python
from django_cognito_m2m.utils import (
    get_client_id,
    get_scopes,
    get_service_principal,
    is_machine_authenticated,
)
```

## Error Semantics

The package keeps authentication and authorization semantics explicit:

- missing token on protected endpoint: `401`
- malformed Authorization header: `401`
- invalid or expired token: `401`
- valid token but missing scopes: `403`
- valid token but client not allowed: `403`

Default plain-Django JSON responses look like:

```json
{"detail": "Authentication credentials were not provided."}
```

```json
{"detail": "Invalid bearer token."}
```

```json
{"detail": "Insufficient scope."}
```

## Security and Design Notes

- Token validation is delegated to `m2m_cognito.CognitoAccessTokenValidator`.
- JWT/JWKS verification is not duplicated in this package.
- Authorization is explicit and endpoint-focused rather than hidden in global magic.
- Invalid bearer tokens are never silently treated as valid identities.
- `request.user` compatibility exists for migration, but `request.auth` and `request.service_principal` remain canonical.

## Testing

The project uses `pytest` and `pytest-django`.

Run the suite with:

```bash
pytest
```

The tests use a fake `m2m_cognito`-compatible validator so they do not depend on live Cognito, live JWTs, or network access to AWS.

The current test coverage includes:

- shared authenticator behavior
- principal normalization
- settings wiring and validator overrides
- DRF authentication and permissions
- method-based and action-based scopes
- middleware, decorators, and CBV mixins
- user mapping strategies and proxy-user behavior
