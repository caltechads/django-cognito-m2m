"""Normalized exceptions exposed by django_cognito_m2m."""

from __future__ import annotations


class DjangoCognitoM2MError(Exception):
    """Base exception for django_cognito_m2m."""


class ConfigurationError(DjangoCognitoM2MError):
    """Raised when package configuration is invalid."""


class AuthenticationError(DjangoCognitoM2MError):
    """Raised when authentication fails."""


class MissingTokenError(AuthenticationError):
    """Raised when a protected endpoint requires a token but none is present."""


class MalformedAuthorizationHeader(AuthenticationError):
    """Raised when the Authorization header is malformed."""


class InvalidTokenError(AuthenticationError):
    """Raised when a bearer token cannot be validated."""


class ExpiredTokenError(InvalidTokenError):
    """Raised when a bearer token is expired."""


class AuthorizationError(DjangoCognitoM2MError):
    """Raised when an authenticated principal is not authorized."""


class InsufficientScopeError(AuthorizationError):
    """Raised when an authenticated principal lacks required scopes."""


class ClientNotAllowedError(AuthorizationError):
    """Raised when a client is not in the allowed client id set."""


class UserMappingError(DjangoCognitoM2MError):
    """Raised when user mapping configuration or execution fails."""
