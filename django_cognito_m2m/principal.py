"""Canonical machine principal representation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from django_cognito_m2m.typing import ClaimsMapping, ScopeMatch


@dataclass(frozen=True, slots=True)
class ServicePrincipal:
    """Immutable authenticated service principal."""

    client_id: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    claims: ClaimsMapping = field(default_factory=dict)
    raw_token: str | None = None

    @property
    def is_authenticated(self) -> bool:
        """Mirror Django's authentication convention."""
        return True

    def has_scope(self, scope: str) -> bool:
        """Return whether the principal has the given scope."""
        return scope in self.scopes

    def has_scopes(self, *scopes: str, match: ScopeMatch = "all") -> bool:
        """Return whether the principal satisfies the given scopes."""
        required = {scope for scope in scopes if scope}
        if not required:
            return True
        if match == "all":
            return required.issubset(self.scopes)
        return bool(required.intersection(self.scopes))

    @property
    def subject(self) -> str | None:
        """Return the JWT subject."""
        return self._get_claim("sub")

    @property
    def audience(self) -> Any:
        """Return the JWT audience claim."""
        return self._get_claim("aud")

    @property
    def issuer(self) -> str | None:
        """Return the JWT issuer claim."""
        return self._get_claim("iss")

    @property
    def expiration(self) -> int | None:
        """Return the JWT expiration timestamp."""
        return self._get_claim("exp")

    @property
    def sub(self) -> str | None:
        """Alias for subject."""
        return self.subject

    @property
    def aud(self) -> Any:
        """Alias for audience."""
        return self.audience

    @property
    def iss(self) -> str | None:
        """Alias for issuer."""
        return self.issuer

    @property
    def exp(self) -> int | None:
        """Alias for expiration."""
        return self.expiration

    def _get_claim(self, key: str) -> Any:
        claims = self.claims
        if isinstance(claims, Mapping):
            return claims.get(key)
        return None
