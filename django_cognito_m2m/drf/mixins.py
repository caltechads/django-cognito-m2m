"""DRF mixins for Cognito M2M integration."""

from __future__ import annotations

from typing import Any

from django_cognito_m2m.conf import cognito_m2m_settings
from django_cognito_m2m.utils import get_service_principal


class CognitoPrincipalMixin:
    """Helper mixin for retrieving the machine principal from DRF views."""

    scope_match = None
    required_scopes = None
    scope_map = None
    action_scope_map = None
    allowed_client_ids = None

    def get_service_principal(self) -> Any:
        """Return the principal attached to the current request."""
        return get_service_principal(self.request)

    def get_scope_match(self) -> str:
        """Return the configured scope matching mode."""
        return getattr(self, "scope_match", None) or cognito_m2m_settings.get("DEFAULT_SCOPE_MATCH")

    def get_required_scopes(self) -> set[str]:
        """Return view-wide required scopes."""
        scopes = getattr(self, "required_scopes", None) or set()
        return set(scopes)

    def get_scope_map(self) -> dict[str, set[str]]:
        """Return method-based scope mappings."""
        scope_map = getattr(self, "scope_map", None) or {}
        return {key.upper(): set(value) for key, value in scope_map.items()}

    def get_action_scope_map(self) -> dict[str, set[str]]:
        """Return action-based scope mappings."""
        action_scope_map = getattr(self, "action_scope_map", None) or {}
        return {key: set(value) for key, value in action_scope_map.items()}

    def get_allowed_client_ids(self) -> set[str] | None:
        """Return allowed client ids for the view."""
        allowed = getattr(self, "allowed_client_ids", None)
        if allowed is None:
            allowed = cognito_m2m_settings.get("ALLOWED_CLIENT_IDS")
        return set(allowed) if allowed else None
