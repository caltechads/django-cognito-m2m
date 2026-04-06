from __future__ import annotations

import pytest
from django.test import RequestFactory, override_settings

from django_cognito_m2m.authenticator import CognitoRequestAuthenticator
from django_cognito_m2m.conf import cognito_m2m_settings
from django_cognito_m2m.exceptions import (
    ExpiredTokenError,
    InsufficientScopeError,
    InvalidTokenError,
    MalformedAuthorizationHeader,
)
from tests import fake_m2m
from tests.support import build_cognito_settings


@pytest.fixture(autouse=True)
def reload_package_settings():
    cognito_m2m_settings.reload()
    yield
    cognito_m2m_settings.reload()


def test_authenticate_request_returns_none_without_header():
    request = RequestFactory().get("/")
    authenticator = CognitoRequestAuthenticator()

    assert authenticator.authenticate_request(request) is None


def test_authenticate_request_returns_none_for_wrong_scheme():
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Token abc")
    authenticator = CognitoRequestAuthenticator()

    assert authenticator.authenticate_request(request) is None


def test_authenticate_request_rejects_malformed_bearer_header():
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer too many parts here")
    authenticator = CognitoRequestAuthenticator()

    with pytest.raises(MalformedAuthorizationHeader):
        authenticator.authenticate_request(request)


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_authenticate_request_returns_normalized_principal():
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer valid-token")
    authenticator = CognitoRequestAuthenticator()

    principal = authenticator.authenticate_request(request)

    assert principal is not None
    assert principal.client_id == "service-client"
    assert principal.scopes == frozenset({"widgets/read", "widgets/write"})
    assert principal.raw_token == "valid-token"
    assert principal.subject == "service-client"
    assert principal.aud == "example-audience"
    assert principal.iss == "issuer"
    assert principal.exp == 9999999999


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_authenticate_request_normalizes_invalid_token_errors():
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer bad-token")
    authenticator = CognitoRequestAuthenticator()

    with pytest.raises(InvalidTokenError):
        authenticator.authenticate_request(request)


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_authenticate_request_normalizes_expired_token_errors():
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer expired-token")
    authenticator = CognitoRequestAuthenticator()

    with pytest.raises(ExpiredTokenError):
        authenticator.authenticate_request(request)


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_authenticate_request_normalizes_upstream_scope_errors():
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer scope-error-token")
    authenticator = CognitoRequestAuthenticator()

    with pytest.raises(InsufficientScopeError):
        authenticator.authenticate_request(request)


@override_settings(
    COGNITO_M2M=build_cognito_settings(
        HEADER_NAME="HTTP_X_API_AUTH",
        HEADER_PREFIX="Token",
        VALIDATOR_KWARGS={"custom": "value"},
    )
)
def test_authenticator_honors_custom_header_prefix_and_validator_kwargs():
    request = RequestFactory().get("/", HTTP_X_API_AUTH="Token valid-token")
    authenticator = CognitoRequestAuthenticator()

    principal = authenticator.authenticate_request(request)

    assert principal is not None
    assert fake_m2m.last_init_kwargs == {
        "region": "us-west-2",
        "user_pool_id": "us-west-2_AbCdEfGhI",
        "audience": "example-audience",
        "custom": "value",
    }


@override_settings(COGNITO_M2M=build_cognito_settings(VALIDATOR_CLASS="tests.fake_m2m.AlternateValidator"))
def test_authenticator_supports_validator_class_override():
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer anything")
    authenticator = CognitoRequestAuthenticator()

    principal = authenticator.authenticate_request(request)

    assert principal is not None
    assert principal.client_id == "alternate-client"
