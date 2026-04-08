"""Utility helpers for request principal access and attachment."""

from __future__ import annotations

from typing import Any

from django_cognito_m2m.conf import CognitoM2MSettings, cognito_m2m_settings
from django_cognito_m2m.principal import ServicePrincipal

_MISSING = object()


def get_underlying_request(request: Any) -> Any:
    """Return the underlying Django request when wrapped by DRF."""
    return getattr(request, "_request", request)


def _get_instance_attr(request: Any, attr: str) -> Any:
    values = getattr(request, "__dict__", None)
    if isinstance(values, dict) and attr in values:
        return values[attr]
    return _MISSING


def _get_request_attr(request: Any, attr: str) -> Any:
    value = _get_instance_attr(request, attr)
    if value is not _MISSING:
        return value
    underlying = get_underlying_request(request)
    if underlying is not request:
        value = _get_instance_attr(underlying, attr)
        if value is not _MISSING:
            return value
    return None


def attach_principal(
    request: Any,
    principal: ServicePrincipal,
    *,
    settings_obj: CognitoM2MSettings | None = None,
) -> ServicePrincipal:
    """Attach the principal to the request using canonical and configured attributes."""
    settings_instance = settings_obj or cognito_m2m_settings
    underlying = get_underlying_request(request)
    attr_names = {
        "service_principal",
        "auth",
        settings_instance.get("REQUEST_PRINCIPAL_ATTR"),
        settings_instance.get("REQUEST_AUTH_ATTR"),
    }
    for attr_name in filter(None, attr_names):
        setattr(request, attr_name, principal)
        if underlying is not request:
            setattr(underlying, attr_name, principal)
    return principal


def attach_user(request: Any, user: Any) -> Any:
    """Attach a resolved user object to the request and underlying request."""
    underlying = get_underlying_request(request)
    setattr(request, "user", user)
    if underlying is not request:
        setattr(underlying, "user", user)
    return user


def get_service_principal(
    request: Any,
    *,
    settings_obj: CognitoM2MSettings | None = None,
) -> ServicePrincipal | None:
    """Return the attached service principal if present."""
    settings_instance = settings_obj or cognito_m2m_settings
    for attr_name in (
        "auth",
        "service_principal",
        settings_instance.get("REQUEST_AUTH_ATTR"),
        settings_instance.get("REQUEST_PRINCIPAL_ATTR"),
    ):
        value = _get_request_attr(request, attr_name)
        if isinstance(value, ServicePrincipal):
            return value
    return None


def get_client_id(request: Any) -> str | None:
    """Return the authenticated client id if available."""
    principal = get_service_principal(request)
    return principal.client_id if principal else None


def get_scopes(request: Any) -> frozenset[str]:
    """Return the authenticated scopes if available."""
    principal = get_service_principal(request)
    return principal.scopes if principal else frozenset()


def is_machine_authenticated(request: Any) -> bool:
    """Return whether a machine principal is attached to the request."""
    principal = get_service_principal(request)
    return bool(principal and principal.is_authenticated)
