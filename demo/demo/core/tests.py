"""API tests for the core book manager endpoints."""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from book_manager.models import Author, Binding, Book, BookAuthor, Publisher


User = get_user_model()


class AuthorAPITests(APITestCase):
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

    def test_list_authors(self) -> None:
        """List authors successfully."""

        response = self.client.get(reverse("author-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["full_name"], "Octavia E. Butler")

    def test_retrieve_author(self) -> None:
        """Retrieve a single author successfully."""

        response = self.client.get(reverse("author-detail", args=[self.author.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.author.pk)

    def test_create_author(self) -> None:
        """Create a new author successfully."""

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

    def test_update_author(self) -> None:
        """Update an existing author successfully."""

        response = self.client.patch(
            reverse("author-detail", args=[self.author.pk]),
            data={"middle_name": ""},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.author.refresh_from_db()
        self.assertEqual(self.author.middle_name, "")

    def test_delete_author(self) -> None:
        """Delete an author successfully."""

        response = self.client.delete(reverse("author-detail", args=[self.author.pk]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Author.objects.filter(pk=self.author.pk).exists())


class BookAPITests(APITestCase):
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

    def test_list_books_includes_ordered_authors(self) -> None:
        """List books with ordered nested authors."""

        response = self.client.get(reverse("book-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        authors = response.data[0]["authors"]
        self.assertEqual([entry["order"] for entry in authors], [1, 2])
        self.assertEqual(
            [entry["author"]["full_name"] for entry in authors],
            ["Ursula K. Le Guin", "N. K. Jemisin"],
        )

    def test_retrieve_book_includes_ordered_authors(self) -> None:
        """Retrieve a single book with ordered nested authors."""

        response = self.client.get(reverse("book-detail", args=[self.book.pk]))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "the-dispossessed")
        self.assertEqual(response.data["authors"][0]["author_id"], self.author_one.pk)

    def test_create_book_persists_ordered_authors(self) -> None:
        """Create a book and matching ordered author assignments."""

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

    def test_update_book_replaces_author_order(self) -> None:
        """Replace existing ordered author assignments on update."""

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

    def test_create_book_accepts_nullable_binding_and_publisher(self) -> None:
        """Allow null foreign keys during book creation."""

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

        response = self.client.post(
            reverse("book-list"),
            data={"authors": [{"author_id": self.author_one.pk, "order": 1}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("title", response.data)

    def test_create_book_rejects_invalid_author(self) -> None:
        """Reject book creation when an author ID does not exist."""

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

        response = self.client.delete(reverse("book-detail", args=[self.book.pk]))

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Book.objects.filter(pk=self.book.pk).exists())
