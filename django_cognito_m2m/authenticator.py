"""Shared request authenticator for Cognito M2M bearer tokens."""

from __future__ import annotations

import logging
from typing import Any

from django_cognito_m2m.conf import CognitoM2MSettings, cognito_m2m_settings
from django_cognito_m2m.exceptions import MalformedAuthorizationHeader
from django_cognito_m2m.principal import ServicePrincipal
from django_cognito_m2m.tracker import track_service_client_activity
from django_cognito_m2m.utils import get_service_principal
from django_cognito_m2m.validator_adapter import ValidatorAdapter

logger = logging.getLogger(__name__)


class CognitoRequestAuthenticator:
    """Extract and validate bearer tokens from Django-style requests."""

    def __init__(
        self,
        *,
        settings_obj: CognitoM2MSettings | None = None,
        validator_adapter: ValidatorAdapter | None = None,
    ) -> None:
        self.settings = settings_obj or cognito_m2m_settings
        self.validator_adapter = validator_adapter or ValidatorAdapter(
            settings_obj=self.settings
        )

    def get_authorization_value(self, request: Any) -> str | None:
        """Return the raw configured authorization header value."""
        value = request.META.get(self.settings.get("HEADER_NAME"))
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("latin1")
        return str(value).strip()

    def extract_bearer_token(self, request: Any) -> str | None:
        """Return the bearer token for the request, if present."""
        header_value = self.get_authorization_value(request)
        if not header_value:
            return None

        parts = header_value.split()
        if not parts:
            return None

        expected_prefix = self.settings.get("HEADER_PREFIX")
        if parts[0].lower() != expected_prefix.lower():
            return None
        if len(parts) != 2 or not parts[1].strip():
            raise MalformedAuthorizationHeader("Malformed Authorization header.")
        return parts[1].strip()

    def authenticate_token(self, token: str) -> ServicePrincipal:
        """Validate a raw token and return a service principal."""
        return self.validator_adapter.validate_token(token)

    def authenticate_request(self, request: Any) -> ServicePrincipal | None:
        """Authenticate a request and return a principal if a bearer token was sent."""
        attached_principal = get_service_principal(request, settings_obj=self.settings)
        if attached_principal is not None:
            return attached_principal

        token = self.extract_bearer_token(request)
        if token is None:
            return None
        principal = self.authenticate_token(token)
        logger.info(
            "token.authenticated, client_id=%s, scopes=%s",
            principal.client_id,
            list(principal.scopes),
        )

        track_service_client_activity(principal, settings_obj=self.settings)
        return principal
