from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings

from django_cognito_m2m.principal import ServicePrincipal
from django_cognito_m2m.user_mapping import ServicePrincipalProxyUser, map_principal_to_user
from django_cognito_m2m.exceptions import UserMappingError
from tests.support import build_cognito_settings


@pytest.mark.django_db
@override_settings(
    COGNITO_M2M=build_cognito_settings(
        USER_MAPPING_ENABLED=True,
        USER_MAPPING_STRATEGY="client_id_field",
        USER_MAPPING_FIELD="username",
    )
)
def test_user_mapping_by_client_id_field(django_user_model):
    user = django_user_model.objects.create_user(username="reporting-client", password="x")
    principal = ServicePrincipal(client_id="reporting-client", scopes=frozenset(), claims={})

    mapped_user = map_principal_to_user(principal)

    assert mapped_user == user


@pytest.mark.django_db
@override_settings(
    COGNITO_M2M=build_cognito_settings(
        USER_MAPPING_ENABLED=True,
        USER_MAPPING_STRATEGY="claim_field",
        USER_MAPPING_FIELD="username",
        USER_MAPPING_CLAIM="sub",
    )
)
def test_user_mapping_by_claim_field(django_user_model):
    user = django_user_model.objects.create_user(username="subject-mapped", password="x")
    principal = ServicePrincipal(client_id="claim-client", scopes=frozenset(), claims={"sub": "subject-mapped"})

    mapped_user = map_principal_to_user(principal)

    assert mapped_user == user


@pytest.mark.django_db
@override_settings(
    COGNITO_M2M=build_cognito_settings(
        USER_MAPPING_ENABLED=True,
        USER_MAPPING_STRATEGY="callable",
        USER_MAPPING_CALLABLE="tests.support.callable_user_mapper",
    )
)
def test_user_mapping_by_callable(django_user_model):
    user = django_user_model.objects.create_user(username="callable-callable-client", password="x")
    principal = ServicePrincipal(client_id="callable-client", scopes=frozenset(), claims={})

    mapped_user = map_principal_to_user(principal)

    assert mapped_user == user


@pytest.mark.django_db
@override_settings(
    COGNITO_M2M=build_cognito_settings(
        USER_MAPPING_ENABLED=True,
        USER_MAPPING_STRATEGY="class",
        USER_MAPPING_CLASS="tests.support.ClassUserMapper",
    )
)
def test_user_mapping_by_class(django_user_model):
    user = django_user_model.objects.create_user(username="class-class-client", password="x")
    principal = ServicePrincipal(client_id="class-client", scopes=frozenset(), claims={})

    mapped_user = map_principal_to_user(principal)

    assert mapped_user == user


@pytest.mark.django_db
@override_settings(
    COGNITO_M2M=build_cognito_settings(
        USER_MAPPING_ENABLED=True,
        USER_MAPPING_STRATEGY="client_id_field",
        USER_MAPPING_FIELD="username",
    )
)
def test_unmapped_principal_falls_back_to_anonymous_user():
    principal = ServicePrincipal(client_id="missing-client", scopes=frozenset(), claims={})

    mapped_user = map_principal_to_user(principal)

    assert isinstance(mapped_user, AnonymousUser)


@override_settings(COGNITO_M2M=build_cognito_settings(RETURN_USER_PROXY=True))
def test_proxy_user_is_returned_when_enabled():
    principal = ServicePrincipal(client_id="proxy-client", scopes=frozenset({"widgets/read"}), claims={})

    mapped_user = map_principal_to_user(principal)

    assert isinstance(mapped_user, ServicePrincipalProxyUser)
    assert mapped_user.client_id == "proxy-client"
    assert mapped_user.is_authenticated is True


@pytest.mark.django_db
@override_settings(
    COGNITO_M2M=build_cognito_settings(
        USER_MAPPING_ENABLED=True,
        USER_MAPPING_STRATEGY="claim_field",
        USER_MAPPING_FIELD="first_name",
        USER_MAPPING_CLAIM="tenant",
    )
)
def test_user_mapping_raises_on_ambiguous_results(django_user_model):
    django_user_model.objects.create_user(username="user-1", password="x", first_name="alpha")
    django_user_model.objects.create_user(username="user-2", password="x", first_name="alpha")
    principal = ServicePrincipal(client_id="ambiguous-client", scopes=frozenset(), claims={"tenant": "alpha"})

    with pytest.raises(UserMappingError):
        map_principal_to_user(principal)
