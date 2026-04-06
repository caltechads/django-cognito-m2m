"""Adapter around m2m_cognito token validation."""

from __future__ import annotations

from typing import Any, Mapping

from django_cognito_m2m.conf import CognitoM2MSettings, cognito_m2m_settings
from django_cognito_m2m.exceptions import (
    ClientNotAllowedError,
    ConfigurationError,
    ExpiredTokenError,
    InsufficientScopeError,
    InvalidTokenError,
)
from django_cognito_m2m.principal import ServicePrincipal


class ValidatorAdapter:
    """Thin adapter around `m2m_cognito.CognitoAccessTokenValidator`."""

    def __init__(
        self,
        *,
        settings_obj: CognitoM2MSettings | None = None,
        validator: Any | None = None,
    ) -> None:
        self.settings = settings_obj or cognito_m2m_settings
        self._validator = validator

    def get_validator(self) -> Any:
        """Return the configured validator instance."""
        if self._validator is None:
            validator_class = self.settings.get_validator_class()
            self._validator = validator_class(**self.settings.build_validator_kwargs())
        return self._validator

    def validate_token(self, token: str) -> ServicePrincipal:
        """Validate a token and normalize it into a service principal."""
        validator = self.get_validator()
        try:
            validated = validator.validate(token)
        except ConfigurationError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize third-party errors centrally
            raise normalize_validation_error(exc) from exc
        return principal_from_validated_token(validated, raw_token=token)


def principal_from_validated_token(validated: Any, *, raw_token: str | None = None) -> ServicePrincipal:
    """Convert an upstream validated token object into a service principal."""
    claims = getattr(validated, "claims", {}) or {}
    scopes = getattr(validated, "scopes", frozenset()) or frozenset()
    client_id = getattr(validated, "client_id", None)
    if not client_id:
        raise InvalidTokenError("Validated token did not include a client_id.")

    normalized_scopes = frozenset(str(scope) for scope in scopes)
    normalized_claims: Mapping[str, Any]
    if isinstance(claims, Mapping):
        normalized_claims = claims
    else:
        normalized_claims = {}

    return ServicePrincipal(
        client_id=str(client_id),
        scopes=normalized_scopes,
        claims=normalized_claims,
        raw_token=raw_token,
    )


def normalize_validation_error(exc: Exception) -> Exception:
    """Map upstream validator errors to local normalized exceptions."""
    if isinstance(exc, (ClientNotAllowedError, ExpiredTokenError, InsufficientScopeError, InvalidTokenError)):
        return exc

    class_name = exc.__class__.__name__
    message = str(exc)
    lowered = message.lower()

    if class_name == "InsufficientScopeError":
        return InsufficientScopeError(message or "Insufficient scope.")
    if "allowed_client_ids" in lowered or "client not allowed" in lowered or "not allowed" in lowered:
        return ClientNotAllowedError(message or "Client is not allowed.")
    if "expired" in lowered or "expiration" in lowered:
        return ExpiredTokenError(message or "Bearer token has expired.")
    if class_name in {"TokenValidationError", "M2MCognitoError"}:
        return InvalidTokenError(message or "Invalid bearer token.")
    return InvalidTokenError(message or "Invalid bearer token.")
