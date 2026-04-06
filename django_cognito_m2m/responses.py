"""HTTP response helpers for authentication and authorization errors."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any, Callable

from django.http import HttpResponse, JsonResponse

from django_cognito_m2m.conf import CognitoM2MSettings, cognito_m2m_settings
from django_cognito_m2m.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ClientNotAllowedError,
    ExpiredTokenError,
    InsufficientScopeError,
    InvalidTokenError,
    MalformedAuthorizationHeader,
    MissingTokenError,
)

ResponseFactory = Callable[[str, int, dict[str, str] | None], HttpResponse]


def default_error_detail(exc: Exception) -> str:
    """Return a user-facing error detail message for a normalized exception."""
    if isinstance(exc, MissingTokenError):
        return "Authentication credentials were not provided."
    if isinstance(exc, MalformedAuthorizationHeader):
        return "Malformed Authorization header."
    if isinstance(exc, ExpiredTokenError):
        return "Bearer token has expired."
    if isinstance(exc, InvalidTokenError):
        return "Invalid bearer token."
    if isinstance(exc, InsufficientScopeError):
        return "Insufficient scope."
    if isinstance(exc, ClientNotAllowedError):
        return "Client is not allowed."
    return str(exc) or "Authentication failed."


def build_error_response(
    detail: str,
    *,
    status_code: int,
    headers: dict[str, str] | None = None,
    response_factory: ResponseFactory | None = None,
    settings_obj: CognitoM2MSettings | None = None,
) -> HttpResponse:
    """Build an API-friendly error response."""
    if response_factory is not None:
        return response_factory(detail, status_code, headers)

    settings_instance = settings_obj or cognito_m2m_settings
    if settings_instance.get("JSON_ERROR_RESPONSES"):
        response: HttpResponse = JsonResponse({"detail": detail}, status=status_code)
    else:
        response = HttpResponse(detail, status=status_code, content_type="text/plain")

    if headers:
        for key, value in headers.items():
            response[key] = value
    return response


def error_response_from_exception(
    exc: Exception,
    *,
    response_factory: ResponseFactory | None = None,
    settings_obj: CognitoM2MSettings | None = None,
) -> HttpResponse:
    """Build an HTTP response for a normalized auth or authorization exception."""
    detail = default_error_detail(exc)
    headers: dict[str, str] | None = None
    if isinstance(exc, AuthenticationError):
        status_code = HTTPStatus.UNAUTHORIZED
        headers = {"WWW-Authenticate": "Bearer"}
    elif isinstance(exc, AuthorizationError):
        status_code = HTTPStatus.FORBIDDEN
    else:
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    return build_error_response(
        detail,
        status_code=int(status_code),
        headers=headers,
        response_factory=response_factory,
        settings_obj=settings_obj,
    )
