"""Decorators for protecting plain Django views with Cognito M2M auth."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from django_cognito_m2m.authenticator import CognitoRequestAuthenticator
from django_cognito_m2m.conf import cognito_m2m_settings
from django_cognito_m2m.exceptions import ClientNotAllowedError, InsufficientScopeError, MissingTokenError
from django_cognito_m2m.responses import ResponseFactory, error_response_from_exception
from django_cognito_m2m.user_mapping import map_principal_to_user
from django_cognito_m2m.utils import attach_principal, attach_user, get_service_principal


def _resolve_principal(request: Any):
    principal = get_service_principal(request, settings_obj=cognito_m2m_settings)
    if principal is not None:
        return principal

    principal = CognitoRequestAuthenticator(settings_obj=cognito_m2m_settings).authenticate_request(request)
    if principal is None:
        raise MissingTokenError("Authentication credentials were not provided.")
    attach_principal(request, principal, settings_obj=cognito_m2m_settings)
    attach_user(request, map_principal_to_user(principal, settings_obj=cognito_m2m_settings))
    return principal


def _enforce_scopes(principal, scopes: set[str], match: str) -> None:
    if scopes and not principal.has_scopes(*sorted(scopes), match=match):
        raise InsufficientScopeError("Insufficient scope.")


def _enforce_client_ids(principal, client_ids: set[str]) -> None:
    if client_ids and principal.client_id not in client_ids:
        raise ClientNotAllowedError("Client is not allowed.")


def _wrap_view(
    view_func: Callable[..., Any],
    *,
    required_scopes: set[str] | None = None,
    allowed_client_ids: set[str] | None = None,
    match: str = "all",
    response_factory: ResponseFactory | None = None,
) -> Callable[..., Any]:
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        try:
            principal = _resolve_principal(request)
            if required_scopes:
                _enforce_scopes(principal, required_scopes, match)
            if allowed_client_ids:
                _enforce_client_ids(principal, allowed_client_ids)
        except Exception as exc:  # noqa: BLE001 - convert normalized auth failures into responses
            return error_response_from_exception(
                exc,
                response_factory=response_factory,
                settings_obj=cognito_m2m_settings,
            )
        return view_func(request, *args, **kwargs)

    return wrapped


def require_authentication(
    view_func: Callable[..., Any] | None = None,
    *,
    response_factory: ResponseFactory | None = None,
):
    """Require a valid Cognito bearer token for a plain Django view."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return _wrap_view(func, response_factory=response_factory)

    if view_func is None:
        return decorator
    return decorator(view_func)


def require_scopes(
    *scopes: str,
    match: str = "all",
    response_factory: ResponseFactory | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require the given scopes for a plain Django view."""

    required_scopes = {scope for scope in scopes if scope}

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return _wrap_view(
            func,
            required_scopes=required_scopes,
            match=match,
            response_factory=response_factory,
        )

    return decorator


def require_any_scope(*scopes: str, response_factory: ResponseFactory | None = None):
    """Require any of the given scopes for a plain Django view."""
    return require_scopes(*scopes, match="any", response_factory=response_factory)


def require_all_scopes(*scopes: str, response_factory: ResponseFactory | None = None):
    """Require all of the given scopes for a plain Django view."""
    return require_scopes(*scopes, match="all", response_factory=response_factory)


def allow_client_ids(
    *client_ids: str,
    response_factory: ResponseFactory | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Require the authenticated client id to appear in the given allowlist."""

    allowed_client_ids = {client_id for client_id in client_ids if client_id}

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return _wrap_view(
            func,
            allowed_client_ids=allowed_client_ids,
            response_factory=response_factory,
        )

    return decorator
