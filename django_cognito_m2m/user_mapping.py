"""Optional Django user mapping for service principals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.utils.module_loading import import_string

from django_cognito_m2m.conf import CognitoM2MSettings, cognito_m2m_settings
from django_cognito_m2m.exceptions import ConfigurationError, UserMappingError
from django_cognito_m2m.principal import ServicePrincipal


@dataclass(frozen=True, slots=True)
class ServicePrincipalProxyUser:
    """A lightweight user-like object that represents a service principal."""

    principal: ServicePrincipal

    @property
    def pk(self) -> None:
        return None

    @property
    def id(self) -> None:
        return None

    @property
    def username(self) -> str:
        return self.principal.client_id

    @property
    def client_id(self) -> str:
        return self.principal.client_id

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    def __str__(self) -> str:
        return self.username


class BaseUserMapper:
    """Base class for custom user mappers."""

    def map_principal_to_user(self, principal: ServicePrincipal) -> Any:
        raise NotImplementedError


class UserMapper:
    """Resolve a Django user for an authenticated service principal."""

    def __init__(self, *, settings_obj: CognitoM2MSettings | None = None) -> None:
        self.settings = settings_obj or cognito_m2m_settings

    def map_principal_to_user(self, principal: ServicePrincipal) -> Any:
        """Resolve the configured user object, proxy user, or anonymous user."""
        if self.settings.get("USER_MAPPING_ENABLED"):
            mapped_user = self._perform_mapping(principal)
            if mapped_user is not None:
                return mapped_user
        if self.settings.get("RETURN_USER_PROXY"):
            return ServicePrincipalProxyUser(principal=principal)
        return AnonymousUser()

    def _perform_mapping(self, principal: ServicePrincipal) -> Any | None:
        strategy = self.settings.get("USER_MAPPING_STRATEGY")
        if strategy is None:
            raise ConfigurationError(
                "COGNITO_M2M['USER_MAPPING_STRATEGY'] is required when user mapping is enabled."
            )
        if strategy == "client_id_field":
            field_name = self.settings.get("USER_MAPPING_FIELD")
            if not field_name:
                raise ConfigurationError(
                    "COGNITO_M2M['USER_MAPPING_FIELD'] is required for client_id_field mapping."
                )
            return self._lookup_user(field_name, principal.client_id)
        if strategy == "claim_field":
            field_name = self.settings.get("USER_MAPPING_FIELD")
            claim_name = self.settings.get("USER_MAPPING_CLAIM")
            if not field_name or not claim_name:
                raise ConfigurationError(
                    "COGNITO_M2M['USER_MAPPING_FIELD'] and ['USER_MAPPING_CLAIM'] are required "
                    "for claim_field mapping."
                )
            claim_value = principal.claims.get(claim_name)
            if claim_value in (None, ""):
                return None
            return self._lookup_user(field_name, claim_value)
        if strategy == "callable":
            mapper = self.settings.import_from_setting("USER_MAPPING_CALLABLE")
            if mapper is None:
                raise ConfigurationError(
                    "COGNITO_M2M['USER_MAPPING_CALLABLE'] is required for callable mapping."
                )
            return self._call_mapper(mapper, principal)
        if strategy == "class":
            mapper_class = self.settings.import_from_setting("USER_MAPPING_CLASS")
            if mapper_class is None:
                raise ConfigurationError(
                    "COGNITO_M2M['USER_MAPPING_CLASS'] is required for class mapping."
                )
            mapper = mapper_class()
            return self._call_mapper(mapper.map_principal_to_user, principal)
        raise ConfigurationError(f"Unsupported user mapping strategy: {strategy!r}.")

    def _lookup_user(self, field_name: str, value: Any) -> Any | None:
        user_model = get_user_model()
        try:
            return user_model._default_manager.get(**{field_name: value})
        except ObjectDoesNotExist:
            return None
        except MultipleObjectsReturned as exc:
            raise UserMappingError(
                f"Multiple users matched {field_name!r} for the authenticated service principal."
            ) from exc
        except Exception as exc:  # noqa: BLE001 - normalize host-project ORM failures
            raise UserMappingError("User mapping lookup failed.") from exc

    def _call_mapper(self, mapper: Any, principal: ServicePrincipal) -> Any | None:
        try:
            return mapper(principal)
        except UserMappingError:
            raise
        except Exception as exc:  # noqa: BLE001 - normalize host-project callback failures
            raise UserMappingError("User mapping callable raised an exception.") from exc


def map_principal_to_user(
    principal: ServicePrincipal,
    *,
    settings_obj: CognitoM2MSettings | None = None,
) -> Any:
    """Map a principal to a Django user-compatible object."""
    return UserMapper(settings_obj=settings_obj).map_principal_to_user(principal)
