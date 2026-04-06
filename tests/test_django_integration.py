from __future__ import annotations

import json

import pytest
from django.http import JsonResponse
from django.test import RequestFactory, override_settings
from django.views import View
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from django_cognito_m2m.django.decorators import allow_client_ids, require_authentication, require_scopes
from django_cognito_m2m.django.middleware import CognitoM2MMiddleware
from django_cognito_m2m.django.mixins import (
    CognitoAuthenticationRequiredMixin,
    CognitoClientIdRequiredMixin,
    CognitoScopeRequiredMixin,
)
from django_cognito_m2m.utils import get_client_id, get_scopes, get_service_principal, is_machine_authenticated
from tests.support import build_cognito_settings


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_middleware_attaches_principal():
    factory = RequestFactory()
    captured = {}

    def get_response(request):
        captured["principal"] = request.service_principal
        captured["auth"] = request.auth
        return JsonResponse({"ok": True})

    middleware = CognitoM2MMiddleware(get_response)
    response = middleware(factory.get("/", HTTP_AUTHORIZATION="Bearer valid-token"))

    assert response.status_code == 200
    assert captured["principal"].client_id == "service-client"
    assert captured["auth"].client_id == "service-client"


@pytest.mark.django_db
@override_settings(
    COGNITO_M2M=build_cognito_settings(
        USER_MAPPING_ENABLED=True,
        USER_MAPPING_STRATEGY="client_id_field",
        USER_MAPPING_FIELD="username",
    )
)
def test_middleware_can_attach_mapped_user(django_user_model):
    django_user_model.objects.create_user(username="reporting-client", password="x")
    captured = {}

    def get_response(request):
        captured["user"] = request.user
        captured["principal"] = request.service_principal
        return JsonResponse({"ok": True})

    middleware = CognitoM2MMiddleware(get_response)
    response = middleware(RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer mapped-user-token"))

    assert response.status_code == 200
    assert captured["user"].username == "reporting-client"
    assert captured["principal"].client_id == "reporting-client"


@override_settings(COGNITO_M2M=build_cognito_settings(RETURN_USER_PROXY=True))
def test_middleware_can_attach_proxy_user():
    captured = {}

    def get_response(request):
        captured["user"] = request.user
        return JsonResponse({"ok": True})

    middleware = CognitoM2MMiddleware(get_response)
    response = middleware(RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer valid-token"))

    assert response.status_code == 200
    assert captured["user"].client_id == "service-client"


@override_settings(COGNITO_M2M=build_cognito_settings(FAIL_ON_INVALID_BEARER=False))
def test_middleware_can_ignore_invalid_bearer_when_configured():
    middleware = CognitoM2MMiddleware(lambda request: JsonResponse({"ok": True}))
    response = middleware(RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer bad-token"))

    assert response.status_code == 200


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_require_authentication_decorator_returns_401_without_token():
    @require_authentication
    def view(request):
        return JsonResponse({"ok": True})

    response = view(RequestFactory().get("/"))

    assert response.status_code == 401
    assert json.loads(response.content) == {"detail": "Authentication credentials were not provided."}


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_require_scopes_decorator_returns_403_for_missing_scope():
    @require_scopes("widgets/read")
    def view(request):
        return JsonResponse({"ok": True})

    response = view(RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer write-token"))

    assert response.status_code == 403
    assert json.loads(response.content) == {"detail": "Insufficient scope."}


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_allow_client_ids_decorator_returns_403_for_disallowed_client():
    @allow_client_ids("service-client")
    def view(request):
        return JsonResponse({"ok": True})

    response = view(RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer other-client-token"))

    assert response.status_code == 403
    assert json.loads(response.content) == {"detail": "Client is not allowed."}


class AuthenticationRequiredView(CognitoAuthenticationRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return JsonResponse({"ok": True})


class ScopeRequiredView(CognitoScopeRequiredMixin, View):
    required_scopes = {"widgets/read"}

    def get(self, request, *args, **kwargs):
        return JsonResponse({"ok": True, "client_id": request.service_principal.client_id})


class ClientIdRequiredView(CognitoClientIdRequiredMixin, View):
    allowed_client_ids = {"service-client"}

    def get(self, request, *args, **kwargs):
        return JsonResponse({"ok": True})


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_cbv_authentication_required_mixin_enforces_authentication():
    response = AuthenticationRequiredView.as_view()(RequestFactory().get("/"))

    assert response.status_code == 401


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_cbv_scope_required_mixin_enforces_scopes():
    response = ScopeRequiredView.as_view()(RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer read-token"))

    assert response.status_code == 200
    assert json.loads(response.content) == {"ok": True, "client_id": "service-client"}


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_cbv_client_id_required_mixin_enforces_allowlist():
    response = ClientIdRequiredView.as_view()(
        RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer other-client-token")
    )

    assert response.status_code == 403


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_request_helpers_work_for_django_and_drf_requests():
    django_request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer valid-token")
    drf_request = Request(APIRequestFactory().get("/", HTTP_AUTHORIZATION="Bearer valid-token"))

    middleware = CognitoM2MMiddleware(lambda request: JsonResponse({"ok": True}))
    middleware(django_request)
    middleware(drf_request._request)

    assert get_client_id(django_request) == "service-client"
    assert get_scopes(django_request) == frozenset({"widgets/read", "widgets/write"})
    assert is_machine_authenticated(django_request) is True
    assert get_service_principal(drf_request).client_id == "service-client"
