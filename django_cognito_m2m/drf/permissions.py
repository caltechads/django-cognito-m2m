"""DRF permission classes for Cognito machine principals."""

from __future__ import annotations

from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.permissions import BasePermission

from django_cognito_m2m.conf import cognito_m2m_settings
from django_cognito_m2m.utils import get_service_principal


def _get_scope_match(view) -> str:
    if hasattr(view, "get_scope_match"):
        return view.get_scope_match()
    return getattr(view, "scope_match", None) or cognito_m2m_settings.get("DEFAULT_SCOPE_MATCH")


def _get_required_scopes(view) -> set[str]:
    if hasattr(view, "get_required_scopes"):
        return set(view.get_required_scopes())
    return set(getattr(view, "required_scopes", None) or set())


def _get_scope_map(view) -> dict[str, set[str]]:
    if hasattr(view, "get_scope_map"):
        return dict(view.get_scope_map())
    scope_map = getattr(view, "scope_map", None) or {}
    return {key.upper(): set(value) for key, value in scope_map.items()}


def _get_action_scope_map(view) -> dict[str, set[str]]:
    if hasattr(view, "get_action_scope_map"):
        return dict(view.get_action_scope_map())
    action_scope_map = getattr(view, "action_scope_map", None) or {}
    return {key: set(value) for key, value in action_scope_map.items()}


def _get_allowed_client_ids(view) -> set[str] | None:
    if hasattr(view, "get_allowed_client_ids"):
        return view.get_allowed_client_ids()
    allowed = getattr(view, "allowed_client_ids", None)
    if allowed is None:
        allowed = cognito_m2m_settings.get("ALLOWED_CLIENT_IDS")
    return set(allowed) if allowed else None


def _require_principal(request):
    principal = get_service_principal(request)
    if principal is None:
        raise NotAuthenticated("Authentication credentials were not provided.")
    return principal


def _enforce_scopes(request, scopes: set[str], match: str) -> bool:
    principal = _require_principal(request)
    if not scopes:
        return True
    if not principal.has_scopes(*sorted(scopes), match=match):
        raise PermissionDenied("Insufficient scope.")
    return True


def _enforce_client_ids(request, allowed_client_ids: set[str] | None) -> bool:
    principal = _require_principal(request)
    if allowed_client_ids and principal.client_id not in allowed_client_ids:
        raise PermissionDenied("Client is not allowed.")
    return True


class HasCognitoScopes(BasePermission):
    """Require `view.required_scopes` using `view.scope_match` or the default match."""

    def has_permission(self, request, view) -> bool:
        return _enforce_scopes(request, _get_required_scopes(view), _get_scope_match(view))


class HasAllCognitoScopes(BasePermission):
    """Require all scopes listed in `view.required_scopes`."""

    def has_permission(self, request, view) -> bool:
        return _enforce_scopes(request, _get_required_scopes(view), "all")


class HasAnyCognitoScope(BasePermission):
    """Require any scope listed in `view.required_scopes`."""

    def has_permission(self, request, view) -> bool:
        return _enforce_scopes(request, _get_required_scopes(view), "any")


class MethodScopePermission(BasePermission):
    """Require method-specific or action-specific scopes."""

    def has_permission(self, request, view) -> bool:
        _require_principal(request)
        action_scope_map = _get_action_scope_map(view)
        if action_scope_map:
            action = getattr(view, "action", None)
            if action and action in action_scope_map:
                return _enforce_scopes(request, set(action_scope_map[action]), _get_scope_match(view))

        scope_map = _get_scope_map(view)
        method_scopes = set(scope_map.get(request.method.upper(), set()))
        return _enforce_scopes(request, method_scopes, _get_scope_match(view))


class AllowedClientIdsPermission(BasePermission):
    """Require the authenticated client id to appear in the configured allowlist."""

    def has_permission(self, request, view) -> bool:
        return _enforce_client_ids(request, _get_allowed_client_ids(view))
