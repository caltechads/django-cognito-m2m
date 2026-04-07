"""Serializers for the core book manager API."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from django.db import transaction
from rest_framework import serializers

from book_manager.models import Author, Binding, Book, BookAuthor, Publisher


class AuthorSerializer(serializers.ModelSerializer):
    """Serialize authors for the API."""

    class Meta:
        model = Author
        fields = [
            "id",
            "created",
            "modified",
            "first_name",
            "last_name",
            "middle_name",
            "full_name",
        ]
        read_only_fields = ["id", "created", "modified"]


class BookAuthorWriteSerializer(serializers.Serializer):
    """Validate ordered author assignments for book writes."""

    author_id = serializers.PrimaryKeyRelatedField(
        queryset=Author.objects.all(),
        source="author",
    )
    order = serializers.IntegerField(min_value=1)


class BookAuthorReadSerializer(serializers.Serializer):
    """Represent ordered author assignments for book reads."""

    author_id = serializers.IntegerField(source="author.id")
    order = serializers.IntegerField()
    author = AuthorSerializer(read_only=True)


class BookSerializer(serializers.ModelSerializer):
    """Serialize books and manage ordered author assignments."""

    binding = serializers.PrimaryKeyRelatedField(
        queryset=Binding.objects.all(),
        allow_null=True,
        required=False,
    )
    publisher = serializers.PrimaryKeyRelatedField(
        queryset=Publisher.objects.all(),
        allow_null=True,
        required=False,
    )
    authors = BookAuthorWriteSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Book
        fields = [
            "id",
            "created",
            "modified",
            "title",
            "slug",
            "isbn",
            "isbn13",
            "num_pages",
            "year_published",
            "original_publication_year",
            "binding",
            "publisher",
            "authors",
        ]
        read_only_fields = ["id", "created", "modified", "slug"]

    def validate_authors(
        self,
        value: Sequence[dict[str, Any]],
    ) -> Sequence[dict[str, Any]]:
        """Validate author uniqueness and ordering.

        Args:
            value: Ordered author assignment payload from the request.

        Raises:
            serializers.ValidationError: Raised when the payload contains
                duplicate authors or duplicate order values.

        Returns:
            The validated author payload unchanged.
        """

        author_ids = [assignment["author"].pk for assignment in value]
        orders = [assignment["order"] for assignment in value]
        if len(author_ids) != len(set(author_ids)):
            raise serializers.ValidationError(
                "Each author may only appear once per book."
            )
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError(
                "Each author assignment order must be unique."
            )
        return value

    @transaction.atomic
    def create(self, validated_data: dict) -> Book:
        """Create a book and its ordered author assignments.

        Side Effects:
            Writes a `Book` row and matching `BookAuthor` rows.

        Args:
            validated_data: Validated serializer data.

        Returns:
            The created book instance.
        """

        author_assignments = validated_data.pop("authors", [])
        book = Book.objects.create(**validated_data)
        self._replace_author_assignments(book=book, author_assignments=author_assignments)
        return book

    @transaction.atomic
    def update(self, instance: Book, validated_data: dict) -> Book:
        """Update a book and replace its ordered author assignments.

        Side Effects:
            Updates the `Book` row and rewrites `BookAuthor` rows when the
            request includes authors.

        Args:
            instance: The existing book instance.
            validated_data: Validated serializer data.

        Returns:
            The updated book instance.
        """

        author_assignments = validated_data.pop("authors", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if author_assignments is not None:
            self._replace_author_assignments(
                book=instance,
                author_assignments=author_assignments,
            )
        return instance

    def to_representation(self, instance: Book) -> dict:
        """Return book data with nested ordered author assignments.

        Args:
            instance: The book instance being serialized.

        Returns:
            A representation of the book suitable for API responses.
        """

        representation = super().to_representation(instance)
        assignments = instance.bookauthor_set.select_related("author").order_by("order")
        representation["authors"] = BookAuthorReadSerializer(assignments, many=True).data
        return representation

    def _replace_author_assignments(
        self,
        *,
        book: Book,
        author_assignments: Sequence[dict[str, Any]],
    ) -> None:
        """Replace all through-table rows for a book.

        Side Effects:
            Deletes and recreates `BookAuthor` rows for the supplied book.

        Keyword Args:
            book: The book whose author assignments should be replaced.
            author_assignments: Ordered author assignment payload.
        """

        book.bookauthor_set.all().delete()
        BookAuthor.objects.bulk_create(
            [
                BookAuthor(
                    book=book,
                    author=assignment["author"],
                    order=assignment["order"],
                )
                for assignment in author_assignments
            ]
        )
