"""Plain Django middleware for Cognito M2M bearer token authentication."""

from __future__ import annotations

from typing import Callable

from django.http import HttpRequest, HttpResponse

from django_cognito_m2m.authenticator import CognitoRequestAuthenticator
from django_cognito_m2m.conf import cognito_m2m_settings
from django_cognito_m2m.exceptions import AuthenticationError
from django_cognito_m2m.responses import error_response_from_exception
from django_cognito_m2m.user_mapping import map_principal_to_user
from django_cognito_m2m.utils import attach_principal, attach_user


class CognitoM2MMiddleware:
    """Attach service principals to incoming Django requests when present."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        self.request_authenticator = CognitoRequestAuthenticator(settings_obj=cognito_m2m_settings)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        try:
            principal = self.request_authenticator.authenticate_request(request)
        except AuthenticationError as exc:
            if cognito_m2m_settings.get("FAIL_ON_INVALID_BEARER"):
                return error_response_from_exception(exc, settings_obj=cognito_m2m_settings)
            principal = None

        if principal is not None:
            attach_principal(request, principal, settings_obj=cognito_m2m_settings)
            user = map_principal_to_user(principal, settings_obj=cognito_m2m_settings)
            attach_user(request, user)

        return self.get_response(request)
