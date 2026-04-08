"""Viewsets for the core book manager API."""

from book_manager.models import Author, Book, BookAuthor
from django.db.models import Prefetch
from rest_framework.viewsets import ModelViewSet

from demo.core.serializers import AuthorSerializer, BookSerializer
from django_cognito_m2m.drf.authentication import CognitoM2MAuthentication
from django_cognito_m2m.drf.permissions import MethodScopePermission

#: Scope required for safe catalog reads.
CATALOG_READ_SCOPE = "cognito_m2m_demo/read"
#: Scope required for catalog mutations.
CATALOG_WRITE_SCOPE = "cognito_m2m_demo/write"


class CognitoProtectedCatalogViewSet(ModelViewSet):
    """Require Cognito auth plus read/write catalog scopes for CRUD actions."""

    authentication_classes = [CognitoM2MAuthentication]
    permission_classes = [MethodScopePermission]
    scope_map = {
        "GET": {CATALOG_READ_SCOPE},
        "HEAD": {CATALOG_READ_SCOPE},
        "OPTIONS": {CATALOG_READ_SCOPE},
        "POST": {CATALOG_WRITE_SCOPE},
        "PUT": {CATALOG_WRITE_SCOPE},
        "PATCH": {CATALOG_WRITE_SCOPE},
        "DELETE": {CATALOG_WRITE_SCOPE},
    }


class AuthorViewSet(CognitoProtectedCatalogViewSet):
    """Expose CRUD operations for authors."""

    queryset = Author.objects.order_by("last_name", "first_name", "middle_name")
    serializer_class = AuthorSerializer


class BookViewSet(CognitoProtectedCatalogViewSet):
    """Expose CRUD operations for books with ordered authors."""

    serializer_class = BookSerializer

    def get_queryset(self):
        """Return books with related data prefetched for API use.

        Returns:
            The optimized queryset for book API responses.
        """

        return Book.objects.select_related("binding", "publisher").prefetch_related(
            Prefetch(
                "bookauthor_set",
                queryset=BookAuthor.objects.select_related("author").order_by("order"),
            )
        )
