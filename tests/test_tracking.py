from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest
from django.test import RequestFactory, override_settings
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from django_cognito_m2m.authenticator import CognitoRequestAuthenticator
from django_cognito_m2m.conf import cognito_m2m_settings
from django_cognito_m2m.drf.authentication import CognitoM2MAuthentication
from django_cognito_m2m.django.middleware import CognitoM2MMiddleware
from django_cognito_m2m.exceptions import ConfigurationError
from django_cognito_m2m.models import ServiceClientActivity
from django_cognito_m2m.principal import ServicePrincipal
from django_cognito_m2m.tracker import track_service_client_activity
from django_cognito_m2m.utils import attach_principal
from tests import fake_m2m
from tests.support import build_cognito_settings


class TrackingProtectedView(APIView):
    authentication_classes = [CognitoM2MAuthentication]

    def get(self, request):
        return Response({"client_id": request.auth.client_id})


@pytest.fixture(autouse=True)
def reload_settings_and_fakes():
    cognito_m2m_settings.reload()
    fake_m2m.validated_tokens.clear()
    yield
    fake_m2m.validated_tokens.clear()
    cognito_m2m_settings.reload()


@pytest.mark.django_db
@override_settings(COGNITO_M2M=build_cognito_settings())
def test_tracking_disabled_does_not_create_activity_rows():
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer valid-token")

    principal = CognitoRequestAuthenticator().authenticate_request(request)

    assert principal is not None
    assert ServiceClientActivity.objects.count() == 0


@pytest.mark.django_db
@override_settings(COGNITO_M2M=build_cognito_settings(TRACK_CLIENT_ACTIVITY=True))
def test_tracking_creates_activity_row_on_first_seen(monkeypatch):
    seen_at = datetime(2026, 4, 8, 12, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr("django_cognito_m2m.tracker.timezone.now", lambda: seen_at)

    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer valid-token")
    principal = CognitoRequestAuthenticator().authenticate_request(request)

    assert principal is not None
    activity = ServiceClientActivity.objects.get(client_id="service-client")
    assert activity.first_seen_at == seen_at
    assert activity.last_seen_at == seen_at


@pytest.mark.django_db
@override_settings(COGNITO_M2M=build_cognito_settings(TRACK_CLIENT_ACTIVITY=True))
def test_tracking_updates_last_seen_without_overwriting_first_seen(monkeypatch):
    first_seen_at = datetime(2026, 4, 8, 12, 0, tzinfo=dt_timezone.utc)
    last_seen_at = datetime(2026, 4, 8, 12, 5, tzinfo=dt_timezone.utc)
    timestamps = iter([first_seen_at, last_seen_at])
    monkeypatch.setattr("django_cognito_m2m.tracker.timezone.now", lambda: next(timestamps))

    authenticator = CognitoRequestAuthenticator()
    authenticator.authenticate_request(RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer valid-token"))
    authenticator.authenticate_request(RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer read-token"))

    activity = ServiceClientActivity.objects.get(client_id="service-client")
    assert ServiceClientActivity.objects.count() == 1
    assert activity.first_seen_at == first_seen_at
    assert activity.last_seen_at == last_seen_at


@override_settings(COGNITO_M2M=build_cognito_settings(TRACK_CLIENT_ACTIVITY=True))
def test_authenticator_reuses_attached_principal_without_revalidating():
    request = RequestFactory().get("/", HTTP_AUTHORIZATION="Bearer valid-token")
    principal = ServicePrincipal(client_id="attached-client", scopes=frozenset({"widgets/read"}))
    attach_principal(request, principal)

    returned = CognitoRequestAuthenticator().authenticate_request(request)

    assert returned is principal
    assert fake_m2m.validated_tokens == []


@pytest.mark.django_db
@override_settings(COGNITO_M2M=build_cognito_settings(TRACK_CLIENT_ACTIVITY=True))
def test_tracking_happens_once_when_middleware_and_drf_share_request(monkeypatch):
    seen_at = datetime(2026, 4, 8, 12, 0, tzinfo=dt_timezone.utc)
    monkeypatch.setattr("django_cognito_m2m.tracker.timezone.now", lambda: seen_at)

    request = APIRequestFactory().get("/", HTTP_AUTHORIZATION="Bearer valid-token")
    request = CognitoM2MMiddleware(lambda incoming_request: incoming_request)(request)
    response = TrackingProtectedView.as_view()(request)

    assert response.status_code == 200
    assert response.data["client_id"] == "service-client"
    assert fake_m2m.validated_tokens == ["valid-token"]
    activity = ServiceClientActivity.objects.get(client_id="service-client")
    assert activity.first_seen_at == seen_at
    assert activity.last_seen_at == seen_at


@override_settings(COGNITO_M2M=build_cognito_settings(TRACK_CLIENT_ACTIVITY=True))
def test_tracking_requires_installed_app(monkeypatch):
    principal = ServicePrincipal(client_id="service-client")
    monkeypatch.setattr("django_cognito_m2m.tracker.apps.is_installed", lambda _: False)

    with pytest.raises(ConfigurationError, match="INSTALLED_APPS"):
        track_service_client_activity(principal)
