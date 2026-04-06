"""Fake m2m_cognito-compatible validator used by tests."""

from __future__ import annotations

from dataclasses import dataclass


class M2MCognitoError(Exception):
    """Base fake upstream error."""


class TokenValidationError(M2MCognitoError):
    """Fake invalid token error."""


class InsufficientScopeError(TokenValidationError):
    """Fake insufficient scope error."""


@dataclass
class FakeValidatedToken:
    client_id: str
    scopes: frozenset[str]
    claims: dict


last_init_kwargs = None


class FakeValidator:
    """Fake validator with deterministic token behaviors."""

    def __init__(self, **kwargs):
        global last_init_kwargs
        last_init_kwargs = kwargs

    def validate(self, token: str):
        if token == "valid-token":
            return FakeValidatedToken(
                client_id="service-client",
                scopes=frozenset({"widgets/read", "widgets/write"}),
                claims={"sub": "service-client", "aud": "example-audience", "iss": "issuer", "exp": 9999999999},
            )
        if token == "read-token":
            return FakeValidatedToken(
                client_id="service-client",
                scopes=frozenset({"widgets/read"}),
                claims={"sub": "service-client"},
            )
        if token == "write-token":
            return FakeValidatedToken(
                client_id="service-client",
                scopes=frozenset({"widgets/write"}),
                claims={"sub": "service-client"},
            )
        if token == "mapped-user-token":
            return FakeValidatedToken(
                client_id="reporting-client",
                scopes=frozenset({"widgets/read"}),
                claims={"sub": "subject-123", "tenant": "alpha"},
            )
        if token == "claim-user-token":
            return FakeValidatedToken(
                client_id="claim-client",
                scopes=frozenset({"widgets/read"}),
                claims={"sub": "subject-mapped"},
            )
        if token == "callable-user-token":
            return FakeValidatedToken(
                client_id="callable-client",
                scopes=frozenset({"widgets/read"}),
                claims={"sub": "callable-subject"},
            )
        if token == "class-user-token":
            return FakeValidatedToken(
                client_id="class-client",
                scopes=frozenset({"widgets/read"}),
                claims={"sub": "class-subject"},
            )
        if token == "other-client-token":
            return FakeValidatedToken(
                client_id="other-client",
                scopes=frozenset({"widgets/read"}),
                claims={"sub": "other-client"},
            )
        if token == "scope-error-token":
            raise InsufficientScopeError("Token scope did not satisfy requirements.")
        if token == "expired-token":
            raise TokenValidationError("Token has expired.")
        if token == "client-denied-token":
            raise TokenValidationError("client not allowed")
        raise TokenValidationError("Token signature was invalid.")


class AlternateValidator:
    """Alternate validator used to verify class overrides."""

    def __init__(self, **kwargs):
        global last_init_kwargs
        last_init_kwargs = kwargs

    def validate(self, token: str):
        return FakeValidatedToken(
            client_id="alternate-client",
            scopes=frozenset({"alt/read"}),
            claims={"sub": token},
        )
