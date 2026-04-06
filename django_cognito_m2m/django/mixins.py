"""Class-based view mixins for Cognito M2M enforcement."""

from __future__ import annotations

from typing import Any

from django_cognito_m2m.authenticator import CognitoRequestAuthenticator
from django_cognito_m2m.conf import cognito_m2m_settings
from django_cognito_m2m.exceptions import ClientNotAllowedError, InsufficientScopeError, MissingTokenError
from django_cognito_m2m.responses import ResponseFactory, error_response_from_exception
from django_cognito_m2m.user_mapping import map_principal_to_user
from django_cognito_m2m.utils import attach_principal, attach_user, get_service_principal


class BaseCognitoViewMixin:
    """Base mixin for enforcing service principal requirements on CBVs."""

    authentication_required = False
    required_scopes: set[str] | None = None
    scope_match = None
    allowed_client_ids: set[str] | None = None
    response_factory: ResponseFactory | None = None

    def get_scope_match(self) -> str:
        return self.scope_match or cognito_m2m_settings.get("DEFAULT_SCOPE_MATCH")

    def get_required_scopes(self) -> set[str]:
        return set(self.required_scopes or set())

    def get_allowed_client_ids(self) -> set[str]:
        allowed = self.allowed_client_ids
        if allowed is None:
            allowed = cognito_m2m_settings.get("ALLOWED_CLIENT_IDS")
        return set(allowed or set())

    def get_response_factory(self) -> ResponseFactory | None:
        return self.response_factory

    def get_service_principal(self):
        principal = get_service_principal(self.request, settings_obj=cognito_m2m_settings)
        if principal is not None:
            return principal

        principal = CognitoRequestAuthenticator(settings_obj=cognito_m2m_settings).authenticate_request(self.request)
        if principal is None:
            raise MissingTokenError("Authentication credentials were not provided.")
        attach_principal(self.request, principal, settings_obj=cognito_m2m_settings)
        attach_user(self.request, map_principal_to_user(principal, settings_obj=cognito_m2m_settings))
        return principal

    def dispatch(self, request, *args, **kwargs):
        self.request = request
        should_authenticate = self.authentication_required or bool(self.get_required_scopes()) or bool(
            self.get_allowed_client_ids()
        )
        if not should_authenticate:
            return super().dispatch(request, *args, **kwargs)

        try:
            principal = self.get_service_principal()
            required_scopes = self.get_required_scopes()
            if required_scopes and not principal.has_scopes(*sorted(required_scopes), match=self.get_scope_match()):
                raise InsufficientScopeError("Insufficient scope.")
            allowed_client_ids = self.get_allowed_client_ids()
            if allowed_client_ids and principal.client_id not in allowed_client_ids:
                raise ClientNotAllowedError("Client is not allowed.")
        except Exception as exc:  # noqa: BLE001 - convert normalized auth failures into responses
            return error_response_from_exception(
                exc,
                response_factory=self.get_response_factory(),
                settings_obj=cognito_m2m_settings,
            )
        return super().dispatch(request, *args, **kwargs)


class CognitoAuthenticationRequiredMixin(BaseCognitoViewMixin):
    """Require a valid machine principal for the view."""

    authentication_required = True


class CognitoScopeRequiredMixin(BaseCognitoViewMixin):
    """Require the configured scopes for the view."""

    authentication_required = True


class CognitoClientIdRequiredMixin(BaseCognitoViewMixin):
    """Require the configured client id allowlist for the view."""

    authentication_required = True
