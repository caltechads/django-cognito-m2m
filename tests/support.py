"""Shared test helpers."""

from __future__ import annotations

from django.contrib.auth import get_user_model


def build_cognito_settings(**overrides):
    settings = {
        "REGION": "us-west-2",
        "USER_POOL_ID": "us-west-2_AbCdEfGhI",
        "VALIDATOR_CLASS": "tests.fake_m2m.FakeValidator",
        "VALIDATOR_KWARGS": {},
        "ALLOWED_CLIENT_IDS": None,
        "AUDIENCE": "example-audience",
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
        "TRACK_CLIENT_ACTIVITY": False,
        "FAIL_ON_INVALID_BEARER": True,
        "JSON_ERROR_RESPONSES": True,
    }
    settings.update(overrides)
    return settings


def callable_user_mapper(principal):
    user_model = get_user_model()
    return user_model.objects.get(username=f"callable-{principal.client_id}")


class ClassUserMapper:
    def map_principal_to_user(self, principal):
        user_model = get_user_model()
        return user_model.objects.get(username=f"class-{principal.client_id}")
