"""API tests for the core book manager endpoints."""

from __future__ import annotations

from dataclasses import dataclass

from book_manager.models import Author, Binding, Book, BookAuthor, Publisher
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()


@dataclass(frozen=True)
class FakeValidatedToken:
    """Represent a validated machine token for test-only auth flows.

    Args:
        client_id: Machine client identifier attached to the request.
        scopes: Authorized scopes for the request.
        claims: Raw token claims exposed on the service principal.
    """

    client_id: str
    scopes: frozenset[str]
    claims: dict[str, str]


class DemoFakeValidator:
    """Return deterministic Cognito-style validation results for demo tests."""

    def __init__(self, **_: object) -> None:
        """Initialize the fake validator.

        Keyword Args:
            **_: Unused keyword arguments accepted for API compatibility.
        """

    def validate(self, token: str) -> FakeValidatedToken:
        """Validate a fake bearer token.

        Args:
            token: Raw bearer token from the request.

        Raises:
            ValueError: Raised when the token should be treated as invalid.

        Returns:
            Deterministic validated token metadata.
        """

        if token == "valid-token":
            return FakeValidatedToken(
                client_id="service-client",
                scopes=frozenset({"cognito_m2m_demo/write", "cognito_m2m_demo/read"}),
                claims={"sub": "service-client"},
            )
        if token == "read-token":
            return FakeValidatedToken(
                client_id="service-client",
                scopes=frozenset({"cognito_m2m_demo/read"}),
                claims={"sub": "service-client"},
            )
        if token == "write-token":
            return FakeValidatedToken(
                client_id="service-client",
                scopes=frozenset({"cognito_m2m_demo/write"}),
                claims={"sub": "service-client"},
            )
        raise ValueError("Token signature was invalid.")


def build_cognito_settings(**overrides: object) -> dict[str, object]:
    """Build deterministic Cognito settings for demo tests.

    Keyword Args:
        **overrides: Settings to override for a specific test case.

    Returns:
        The demo's `COGNITO_M2M` settings dictionary.
    """

    settings = {
        "REGION": "us-west-2",
        "USER_POOL_ID": "us-west-2_AbCdEfGhI",
        "AUDIENCE": "demo-audience",
        "VALIDATOR_CLASS": DemoFakeValidator,
        "VALIDATOR_KWARGS": {},
        "ALLOWED_CLIENT_IDS": None,
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
        "TRACK_CLIENT_ACTIVITY": False,
        "FAIL_ON_INVALID_BEARER": True,
        "JSON_ERROR_RESPONSES": True,
    }
    settings.update(overrides)
    return settings


@override_settings(COGNITO_M2M=build_cognito_settings())
class AuthenticatedAPITestCase(APITestCase):
    """Provide shared helpers for authenticated API tests."""

    def authenticate(self, token: str) -> None:
        """Attach a bearer token to the test client.

        Args:
            token: Fake bearer token string.
        """

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def assert_machine_principal(
        self,
        response,
        *,
        client_id: str,
        scopes: frozenset[str],
    ) -> None:
        """Assert the authenticated request exposes the expected principal.

        Args:
            response: Django test response from an authenticated request.
            client_id: Expected machine client id.
            scopes: Expected principal scopes.
        """

        request = response.wsgi_request
        self.assertTrue(request.user.is_anonymous)
        self.assertIs(request.auth, request.service_principal)
        self.assertEqual(request.auth.client_id, client_id)
        self.assertEqual(request.auth.scopes, scopes)


class AuthorAPITests(AuthenticatedAPITestCase):
    """Verify CRUD behavior for author API endpoints."""

    def setUp(self) -> None:
        """Create sample authors for each test."""

        super().setUp()
        self.author = Author.objects.create(
            first_name="Octavia",
            last_name="Butler",
            middle_name="E.",
            full_name="Octavia E. Butler",
        )

    def test_list_authors_requires_authentication(self) -> None:
        """Reject unauthenticated author list requests."""

        response = self.client.get(reverse("author-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.data["detail"],
            "Authentication credentials were not provided.",
        )

    def test_list_authors_rejects_invalid_token(self) -> None:
        """Reject author list requests with an invalid token."""

        self.authenticate("bad-token")

        response = self.client.get(reverse("author-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Token signature was invalid.")

    def test_list_authors(self) -> None:
        """List authors successfully."""

        self.authenticate("read-token")
        response = self.client.get(reverse("author-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["full_name"], "Octavia E. Butler")
        self.assert_machine_principal(
            response,
            client_id="service-client",
            scopes=frozenset({"cognito_m2m_demo/read"}),
        )

    def test_retrieve_author(self) -> None:
        """Retrieve a single author successfully."""

        self.authenticate("read-token")
        response = self.client.get(reverse("author-detail", args=[self.author.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.author.pk)

    def test_create_author(self) -> None:
        """Create a new author successfully."""

        self.authenticate("write-token")
        response = self.client.post(
            reverse("author-list"),
            data={
                "first_name": "Nnedi",
                "last_name": "Okorafor",
                "middle_name": "",
                "full_name": "Nnedi Okorafor",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Author.objects.filter(full_name="Nnedi Okorafor").exists())

    def test_create_author_rejects_read_only_token(self) -> None:
        """Reject author creation when only the read scope is present."""

        self.authenticate("read-token")

        response = self.client.post(
            reverse("author-list"),
            data={
                "first_name": "Nnedi",
                "last_name": "Okorafor",
                "middle_name": "",
                "full_name": "Nnedi Okorafor",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "Insufficient scope.")

    def test_update_author(self) -> None:
        """Update an existing author successfully."""

        self.authenticate("write-token")
        response = self.client.patch(
            reverse("author-detail", args=[self.author.pk]),
            data={"middle_name": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.author.refresh_from_db()
        self.assertEqual(self.author.middle_name, "")

    def test_retrieve_author_rejects_write_only_token(self) -> None:
        """Reject author retrieval when the read scope is missing."""

        self.authenticate("write-token")

        response = self.client.get(reverse("author-detail", args=[self.author.pk]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "Insufficient scope.")

    def test_delete_author(self) -> None:
        """Delete an author successfully."""

        self.authenticate("write-token")
        response = self.client.delete(reverse("author-detail", args=[self.author.pk]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Author.objects.filter(pk=self.author.pk).exists())

    def test_valid_token_supports_full_author_crud_flow(self) -> None:
        """Allow a token with both scopes to complete a full CRUD flow."""

        self.authenticate("valid-token")

        create_response = self.client.post(
            reverse("author-list"),
            data={
                "first_name": "Ann",
                "last_name": "Leckie",
                "middle_name": "",
                "full_name": "Ann Leckie",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        author_id = create_response.data["id"]

        list_response = self.client.get(reverse("author-list"))
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        update_response = self.client.patch(
            reverse("author-detail", args=[author_id]),
            data={"middle_name": "A."},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)

        delete_response = self.client.delete(reverse("author-detail", args=[author_id]))
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)


@override_settings(COGNITO_M2M=build_cognito_settings())
class BookAPITests(AuthenticatedAPITestCase):
    """Verify CRUD behavior for book API endpoints."""

    def setUp(self) -> None:
        """Create related model fixtures for book endpoint tests."""

        super().setUp()
        self.reader = User.objects.create_user(
            username="reader",
            password="test-password",
        )
        self.binding = Binding.objects.create(name="Hardcover")
        self.publisher = Publisher.objects.create(name="Tor")
        self.author_one = Author.objects.create(
            first_name="Ursula",
            last_name="Le Guin",
            middle_name="K.",
            full_name="Ursula K. Le Guin",
        )
        self.author_two = Author.objects.create(
            first_name="N.",
            last_name="Jemisin",
            middle_name="K.",
            full_name="N. K. Jemisin",
        )
        self.book = Book.objects.create(
            title="The Dispossessed",
            isbn="1234567890",
            binding=self.binding,
            publisher=self.publisher,
        )
        BookAuthor.objects.create(book=self.book, author=self.author_one, order=1)
        BookAuthor.objects.create(book=self.book, author=self.author_two, order=2)

    def test_list_books_requires_authentication(self) -> None:
        """Reject unauthenticated book list requests."""

        response = self.client.get(reverse("book-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            response.data["detail"],
            "Authentication credentials were not provided.",
        )

    def test_list_books_rejects_invalid_token(self) -> None:
        """Reject book list requests with an invalid token."""

        self.authenticate("bad-token")

        response = self.client.get(reverse("book-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Token signature was invalid.")

    def test_list_books_includes_ordered_authors(self) -> None:
        """List books with ordered nested authors."""

        self.authenticate("read-token")
        response = self.client.get(reverse("book-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        authors = response.data[0]["authors"]
        self.assertEqual([entry["order"] for entry in authors], [1, 2])
        self.assertEqual(
            [entry["author"]["full_name"] for entry in authors],
            ["Ursula K. Le Guin", "N. K. Jemisin"],
        )
        self.assert_machine_principal(
            response,
            client_id="service-client",
            scopes=frozenset({"cognito_m2m_demo/read"}),
        )

    def test_retrieve_book_includes_ordered_authors(self) -> None:
        """Retrieve a single book with ordered nested authors."""

        self.authenticate("read-token")
        response = self.client.get(reverse("book-detail", args=[self.book.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "the-dispossessed")
        self.assertEqual(response.data["authors"][0]["author_id"], self.author_one.pk)

    def test_create_book_persists_ordered_authors(self) -> None:
        """Create a book and matching ordered author assignments."""

        self.authenticate("write-token")
        response = self.client.post(
            reverse("book-list"),
            data={
                "title": "The Fifth Season",
                "isbn": "0987654321",
                "isbn13": "9780316229296",
                "num_pages": 512,
                "year_published": 2015,
                "original_publication_year": 2015,
                "binding": self.binding.pk,
                "publisher": self.publisher.pk,
                "authors": [
                    {"author_id": self.author_two.pk, "order": 1},
                    {"author_id": self.author_one.pk, "order": 2},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        book = Book.objects.get(title="The Fifth Season")
        assignments = list(
            book.bookauthor_set.order_by("order").values_list("author_id", "order")
        )
        self.assertEqual(
            assignments,
            [(self.author_two.pk, 1), (self.author_one.pk, 2)],
        )

    def test_create_book_rejects_read_only_token(self) -> None:
        """Reject book creation when only the read scope is present."""

        self.authenticate("read-token")

        response = self.client.post(
            reverse("book-list"),
            data={
                "title": "Forbidden Book",
                "authors": [{"author_id": self.author_one.pk, "order": 1}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "Insufficient scope.")

    def test_update_book_replaces_author_order(self) -> None:
        """Replace existing ordered author assignments on update."""

        self.authenticate("write-token")
        response = self.client.patch(
            reverse("book-detail", args=[self.book.pk]),
            data={
                "authors": [
                    {"author_id": self.author_two.pk, "order": 1},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assignments = list(
            self.book.bookauthor_set.order_by("order").values_list("author_id", "order")
        )
        self.assertEqual(assignments, [(self.author_two.pk, 1)])

    def test_retrieve_book_rejects_write_only_token(self) -> None:
        """Reject book retrieval when the read scope is missing."""

        self.authenticate("write-token")

        response = self.client.get(reverse("book-detail", args=[self.book.pk]))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["detail"], "Insufficient scope.")

    def test_create_book_accepts_nullable_binding_and_publisher(self) -> None:
        """Allow null foreign keys during book creation."""

        self.authenticate("write-token")
        response = self.client.post(
            reverse("book-list"),
            data={
                "title": "Parable of the Sower",
                "binding": None,
                "publisher": None,
                "authors": [{"author_id": self.author_one.pk, "order": 1}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        book = Book.objects.get(title="Parable of the Sower")
        self.assertIsNone(book.binding)
        self.assertIsNone(book.publisher)

    def test_create_book_requires_title(self) -> None:
        """Reject book creation when the title is missing."""

        self.authenticate("write-token")
        response = self.client.post(
            reverse("book-list"),
            data={"authors": [{"author_id": self.author_one.pk, "order": 1}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_create_book_rejects_invalid_author(self) -> None:
        """Reject book creation when an author ID does not exist."""

        self.authenticate("write-token")
        response = self.client.post(
            reverse("book-list"),
            data={
                "title": "Invalid Author Book",
                "authors": [{"author_id": 999999, "order": 1}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("authors", response.data)

    def test_create_book_rejects_duplicate_author_entries(self) -> None:
        """Reject duplicate authors in a single book payload."""

        self.authenticate("write-token")
        response = self.client.post(
            reverse("book-list"),
            data={
                "title": "Duplicate Author Book",
                "authors": [
                    {"author_id": self.author_one.pk, "order": 1},
                    {"author_id": self.author_one.pk, "order": 2},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("authors", response.data)

    def test_create_book_rejects_duplicate_order_values(self) -> None:
        """Reject duplicate author order values in a single payload."""

        self.authenticate("write-token")
        response = self.client.post(
            reverse("book-list"),
            data={
                "title": "Duplicate Order Book",
                "authors": [
                    {"author_id": self.author_one.pk, "order": 1},
                    {"author_id": self.author_two.pk, "order": 1},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("authors", response.data)

    def test_create_book_rejects_malformed_author_entries(self) -> None:
        """Reject malformed nested author payloads."""

        self.authenticate("write-token")
        response = self.client.post(
            reverse("book-list"),
            data={
                "title": "Malformed Author Book",
                "authors": [{"author_id": self.author_one.pk}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("authors", response.data)

    def test_delete_book(self) -> None:
        """Delete a book successfully."""

        self.authenticate("write-token")
        response = self.client.delete(reverse("book-detail", args=[self.book.pk]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Book.objects.filter(pk=self.book.pk).exists())
