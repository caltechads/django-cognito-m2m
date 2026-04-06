"""Shared typing helpers for django_cognito_m2m."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Protocol, TypeAlias


ScopeMatch: TypeAlias = Literal["all", "any"]
ClaimsMapping: TypeAlias = Mapping[str, Any]


class UserMapperProtocol(Protocol):
    """Protocol for user mappers."""

    def map_principal_to_user(self, principal: Any) -> Any:
        """Return a Django user-like object for the provided principal."""
