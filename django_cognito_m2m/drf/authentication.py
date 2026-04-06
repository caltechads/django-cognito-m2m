"""DRF authentication backend for Cognito M2M bearer tokens."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

from django_cognito_m2m.authenticator import CognitoRequestAuthenticator
from django_cognito_m2m.conf import cognito_m2m_settings
from django_cognito_m2m.exceptions import AuthenticationError
from django_cognito_m2m.user_mapping import map_principal_to_user
from django_cognito_m2m.utils import attach_principal, attach_user


class CognitoM2MAuthentication(BaseAuthentication):
    """Authenticate Cognito M2M bearer tokens for DRF views."""

    def __init__(self) -> None:
        self.request_authenticator = CognitoRequestAuthenticator(settings_obj=cognito_m2m_settings)

    def authenticate(self, request):
        try:
            principal = self.request_authenticator.authenticate_request(request)
        except AuthenticationError as exc:
            raise exceptions.AuthenticationFailed(str(exc) or "Authentication failed.") from exc

        if principal is None:
            return None

        attach_principal(request, principal, settings_obj=cognito_m2m_settings)
        user = map_principal_to_user(principal, settings_obj=cognito_m2m_settings)
        if user is None:
            user = AnonymousUser()
        attach_user(request, user)
        return (user, principal)

    def authenticate_header(self, request) -> str:
        return cognito_m2m_settings.get("HEADER_PREFIX")
