from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from django_cognito_m2m.drf.authentication import CognitoM2MAuthentication
from django_cognito_m2m.drf.mixins import CognitoPrincipalMixin
from django_cognito_m2m.drf.permissions import (
    AllowedClientIdsPermission,
    HasCognitoScopes,
    MethodScopePermission,
)
from tests.support import build_cognito_settings


class ProtectedScopeView(CognitoPrincipalMixin, APIView):
    authentication_classes = [CognitoM2MAuthentication]
    permission_classes = [HasCognitoScopes]
    required_scopes = {"widgets/read"}

    def get(self, request):
        principal = request.auth
        return Response(
            {
                "client_id": principal.client_id,
                "scopes": sorted(principal.scopes),
                "service_principal": getattr(request, "service_principal").client_id,
                "user": getattr(request.user, "username", None),
                "anonymous": bool(getattr(request.user, "is_anonymous", False)),
            }
        )


class MethodScopedView(APIView):
    authentication_classes = [CognitoM2MAuthentication]
    permission_classes = [MethodScopePermission]
    scope_map = {
        "GET": {"widgets/read"},
        "POST": {"widgets/write"},
    }

    def get(self, request):
        return Response({"ok": True})

    def post(self, request):
        return Response({"ok": True})


class ClientAllowlistView(APIView):
    authentication_classes = [CognitoM2MAuthentication]
    permission_classes = [AllowedClientIdsPermission]
    allowed_client_ids = {"service-client"}

    def get(self, request):
        return Response({"client_id": request.auth.client_id})


class ActionScopedViewSet(ViewSet):
    authentication_classes = [CognitoM2MAuthentication]
    permission_classes = [MethodScopePermission]
    action_scope_map = {
        "list": {"widgets/read"},
        "create": {"widgets/write"},
    }

    def list(self, request):
        return Response({"ok": True})

    def create(self, request):
        return Response({"ok": True})


class HeaderUserAuthentication(BaseAuthentication):
    def authenticate(self, request):
        username = request.META.get("HTTP_X_TEST_USER")
        if not username:
            return None
        user = get_user_model()(username=username)
        return (user, None)


class MixedAuthenticationView(APIView):
    authentication_classes = [CognitoM2MAuthentication, HeaderUserAuthentication]

    def get(self, request):
        return Response(
            {
                "user": getattr(request.user, "username", None),
                "principal": getattr(getattr(request, "auth", None), "client_id", None),
            }
        )


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_drf_valid_token_succeeds_on_protected_api():
    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION="Bearer valid-token")
    response = ProtectedScopeView.as_view()(request)

    assert response.status_code == 200
    assert response.data["client_id"] == "service-client"
    assert response.data["service_principal"] == "service-client"
    assert response.data["anonymous"] is True


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_drf_invalid_token_returns_401():
    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION="Bearer bad-token")
    response = ProtectedScopeView.as_view()(request)

    assert response.status_code == 401
    assert response.data["detail"] == "Token signature was invalid."


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_drf_missing_token_returns_401():
    request = APIRequestFactory().get("/")
    response = ProtectedScopeView.as_view()(request)

    assert response.status_code == 401
    assert response.data["detail"] == "Authentication credentials were not provided."


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_drf_valid_token_without_required_scope_returns_403():
    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION="Bearer write-token")
    response = ProtectedScopeView.as_view()(request)

    assert response.status_code == 403
    assert response.data["detail"] == "Insufficient scope."


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_drf_method_based_scopes_are_enforced():
    factory = APIRequestFactory()

    get_response = MethodScopedView.as_view()(factory.get("/", HTTP_AUTHORIZATION="Bearer read-token"))
    post_response_forbidden = MethodScopedView.as_view()(factory.post("/", {}, format="json", HTTP_AUTHORIZATION="Bearer read-token"))
    post_response_allowed = MethodScopedView.as_view()(factory.post("/", {}, format="json", HTTP_AUTHORIZATION="Bearer write-token"))

    assert get_response.status_code == 200
    assert post_response_forbidden.status_code == 403
    assert post_response_allowed.status_code == 200


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_drf_action_based_scopes_are_enforced():
    factory = APIRequestFactory()
    list_view = ActionScopedViewSet.as_view({"get": "list"})
    create_view = ActionScopedViewSet.as_view({"post": "create"})

    list_response = list_view(factory.get("/", HTTP_AUTHORIZATION="Bearer read-token"))
    create_response = create_view(factory.post("/", {}, format="json", HTTP_AUTHORIZATION="Bearer read-token"))

    assert list_response.status_code == 200
    assert create_response.status_code == 403


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_drf_allowed_client_ids_permission():
    factory = APIRequestFactory()

    allowed = ClientAllowlistView.as_view()(factory.get("/", HTTP_AUTHORIZATION="Bearer read-token"))
    forbidden = ClientAllowlistView.as_view()(factory.get("/", HTTP_AUTHORIZATION="Bearer other-client-token"))

    assert allowed.status_code == 200
    assert forbidden.status_code == 403
    assert forbidden.data["detail"] == "Client is not allowed."


@pytest.mark.django_db
@override_settings(
    COGNITO_M2M=build_cognito_settings(
        USER_MAPPING_ENABLED=True,
        USER_MAPPING_STRATEGY="client_id_field",
        USER_MAPPING_FIELD="username",
    )
)
def test_drf_can_map_service_principal_to_user(django_user_model):
    django_user_model.objects.create_user(username="reporting-client", password="x")
    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION="Bearer mapped-user-token")
    response = ProtectedScopeView.as_view()(request)

    assert response.status_code == 200
    assert response.data["user"] == "reporting-client"
    assert response.data["client_id"] == "reporting-client"


@override_settings(COGNITO_M2M=build_cognito_settings(RETURN_USER_PROXY=True))
def test_drf_can_return_proxy_user():
    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION="Bearer valid-token")
    response = ProtectedScopeView.as_view()(request)

    assert response.status_code == 200
    assert response.data["user"] == "service-client"
    assert response.data["anonymous"] is False


@override_settings(COGNITO_M2M=build_cognito_settings())
def test_drf_coexists_with_other_authentication_classes():
    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION="Token ignored", HTTP_X_TEST_USER="browser-user")
    response = MixedAuthenticationView.as_view()(request)

    assert response.status_code == 200
    assert response.data == {"user": "browser-user", "principal": None}
