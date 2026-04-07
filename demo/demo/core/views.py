"""Viewsets for the core book manager API."""

from django.db.models import Prefetch
from rest_framework.viewsets import ModelViewSet

from book_manager.models import Author, Book, BookAuthor

from demo.core.serializers import AuthorSerializer, BookSerializer


class AuthorViewSet(ModelViewSet):
    """Expose CRUD operations for authors."""

    queryset = Author.objects.order_by("last_name", "first_name", "middle_name")
    serializer_class = AuthorSerializer


class BookViewSet(ModelViewSet):
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
