"""Minimal Django settings for the test suite."""

SECRET_KEY = "test-secret-key"
DEBUG = True
USE_TZ = True
ROOT_URLCONF = "tests.urls"
ALLOWED_HOSTS = ["*"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "django_cognito_m2m",
]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
COGNITO_M2M = {
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
    "FAIL_ON_INVALID_BEARER": True,
    "JSON_ERROR_RESPONSES": True,
}
