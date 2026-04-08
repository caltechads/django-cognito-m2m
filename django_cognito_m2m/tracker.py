"""Persistence helpers for authenticated client activity."""

from __future__ import annotations

from django.apps import apps
from django.db import IntegrityError, OperationalError, ProgrammingError
from django.utils import timezone

from django_cognito_m2m.conf import CognitoM2MSettings, cognito_m2m_settings
from django_cognito_m2m.exceptions import ConfigurationError
from django_cognito_m2m.principal import ServicePrincipal


def track_service_client_activity(
    principal: ServicePrincipal,
    *,
    settings_obj: CognitoM2MSettings | None = None,
) -> None:
    """Create or update the activity row for an authenticated client."""

    settings_instance = settings_obj or cognito_m2m_settings
    if not settings_instance.get("TRACK_CLIENT_ACTIVITY"):
        return

    if not apps.is_installed("django_cognito_m2m"):
        raise ConfigurationError(
            "COGNITO_M2M['TRACK_CLIENT_ACTIVITY']=True requires "
            "'django_cognito_m2m' in INSTALLED_APPS and a migrated database."
        )

    try:
        model = apps.get_model("django_cognito_m2m", "ServiceClientActivity")
    except LookupError as exc:
        raise ConfigurationError(
            "COGNITO_M2M['TRACK_CLIENT_ACTIVITY']=True requires "
            "'django_cognito_m2m' in INSTALLED_APPS and a migrated database."
        ) from exc

    now = timezone.now()

    try:
        updated = model.objects.filter(client_id=principal.client_id).update(last_seen_at=now)
        if updated:
            return
        model.objects.create(client_id=principal.client_id, first_seen_at=now, last_seen_at=now)
    except IntegrityError:
        model.objects.filter(client_id=principal.client_id).update(last_seen_at=now)
    except (OperationalError, ProgrammingError) as exc:
        raise ConfigurationError(
            "COGNITO_M2M['TRACK_CLIENT_ACTIVITY']=True requires the "
            "'django_cognito_m2m_serviceclientactivity' table. Add 'django_cognito_m2m' "
            "to INSTALLED_APPS and run 'python manage.py migrate'."
        ) from exc
