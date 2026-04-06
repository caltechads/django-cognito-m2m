"""Settings helpers for django_cognito_m2m."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.conf import settings
from django.test.signals import setting_changed
from django.utils.module_loading import import_string

from django_cognito_m2m.exceptions import ConfigurationError


DEFAULTS: dict[str, Any] = {
    "REGION": None,
    "USER_POOL_ID": None,
    "VALIDATOR_CLASS": None,
    "VALIDATOR_KWARGS": {},
    "ALLOWED_CLIENT_IDS": None,
    "AUDIENCE": None,
    "HEADER_NAME": "HTTP_AUTHORIZATION",
    "HEADER_PREFIX": "Bearer",
    "REQUEST_PRINCIPAL_ATTR": "service_principal",
    "REQUEST_AUTH_ATTR": "auth",
    "DEFAULT_SCOPE_MATCH": "all",
    "USER_MAPPING_ENABLED": False,
    "USER_MAPPING_STRATEGY": None,
    "USER_MAPPING_FIELD": None,
    "USER_MAPPING_CLAIM": None,
    "USER_MAPPING_CALLABLE": None,
    "USER_MAPPING_CLASS": None,
    "RETURN_USER_PROXY": False,
    "FAIL_ON_INVALID_BEARER": True,
    "JSON_ERROR_RESPONSES": True,
}

VALID_SCOPE_MATCHES = {"all", "any"}
VALID_USER_MAPPING_STRATEGIES = {None, "client_id_field", "claim_field", "callable", "class"}


class CognitoM2MSettings:
    """Lazy wrapper around Django settings."""

    setting_name = "COGNITO_M2M"

    def __init__(self) -> None:
        self._cached: dict[str, Any] | None = None

    def reload(self) -> None:
        """Clear any cached settings."""
        self._cached = None

    @property
    def values(self) -> dict[str, Any]:
        """Return merged settings with defaults."""
        if self._cached is None:
            user_settings = getattr(settings, self.setting_name, {})
            merged = deepcopy(DEFAULTS)
            merged.update(user_settings)
            self._validate(merged)
            self._cached = merged
        return self._cached

    def _validate(self, values: dict[str, Any]) -> None:
        if values["DEFAULT_SCOPE_MATCH"] not in VALID_SCOPE_MATCHES:
            raise ConfigurationError("COGNITO_M2M['DEFAULT_SCOPE_MATCH'] must be 'all' or 'any'.")
        if values["USER_MAPPING_STRATEGY"] not in VALID_USER_MAPPING_STRATEGIES:
            raise ConfigurationError(
                "COGNITO_M2M['USER_MAPPING_STRATEGY'] must be one of "
                f"{sorted(item for item in VALID_USER_MAPPING_STRATEGIES if item is not None)} or None."
            )
        if not isinstance(values["VALIDATOR_KWARGS"], dict):
            raise ConfigurationError("COGNITO_M2M['VALIDATOR_KWARGS'] must be a dictionary.")
        if not values["HEADER_NAME"]:
            raise ConfigurationError("COGNITO_M2M['HEADER_NAME'] must not be empty.")
        if not values["HEADER_PREFIX"]:
            raise ConfigurationError("COGNITO_M2M['HEADER_PREFIX'] must not be empty.")

    def get(self, name: str) -> Any:
        """Return a configured setting."""
        return self.values[name]

    def import_from_setting(self, name: str) -> Any:
        """Import a dotted-path setting if provided."""
        value = self.get(name)
        if value is None or value == "":
            return None
        if isinstance(value, str):
            return import_string(value)
        return value

    def get_validator_class(self) -> type[Any]:
        """Return the configured validator class."""
        value = self.get("VALIDATOR_CLASS")
        if value:
            imported = self.import_from_setting("VALIDATOR_CLASS")
            if not isinstance(imported, type):
                raise ConfigurationError("COGNITO_M2M['VALIDATOR_CLASS'] must resolve to a class.")
            return imported

        try:
            validator_class = import_string("m2m_cognito.CognitoAccessTokenValidator")
        except Exception as exc:  # pragma: no cover - exercised in environments without dependency
            raise ConfigurationError(
                "m2m_cognito is not importable. Install the m2m-cognito dependency "
                "or configure COGNITO_M2M['VALIDATOR_CLASS']."
            ) from exc
        return validator_class

    def build_validator_kwargs(self) -> dict[str, Any]:
        """Build validator initialization kwargs."""
        region = self.get("REGION")
        user_pool_id = self.get("USER_POOL_ID")
        if not region:
            raise ConfigurationError("COGNITO_M2M['REGION'] is required.")
        if not user_pool_id:
            raise ConfigurationError("COGNITO_M2M['USER_POOL_ID'] is required.")

        kwargs = {
            "region": region,
            "user_pool_id": user_pool_id,
        }
        audience = self.get("AUDIENCE")
        if audience is not None:
            kwargs["audience"] = audience
        kwargs.update(self.get("VALIDATOR_KWARGS"))
        return kwargs


cognito_m2m_settings = CognitoM2MSettings()


def _reload_settings(*_: Any, **kwargs: Any) -> None:
    if kwargs.get("setting") == "COGNITO_M2M":
        cognito_m2m_settings.reload()


setting_changed.connect(_reload_settings)
