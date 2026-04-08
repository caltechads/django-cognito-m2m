"""Exercise the authenticated demo DRF author/book endpoints end to end.

This script talks to a locally running Django server and performs a small
author/book lifecycle against the protected `/api/` endpoints. It is intentionally
lightweight and uses only the Python standard library so it is easy to rerun in
the demo environment.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


#: Default base URL for the locally running Django server.
DEFAULT_BASE_URL = "http://127.0.0.1:8000"


@dataclass(frozen=True)
class ApiResponse:
    """Represent a decoded JSON API response.

    Args:
        status_code: HTTP status code from the response.
        data: JSON-decoded response payload, or raw text when decoding fails.
    """

    #: HTTP status code returned by the API.
    status_code: int
    #: Parsed response payload.
    data: Any


class ApiClient:
    """Make JSON requests against the demo API.

    The client centralizes header handling so every request consistently sends
    the required bearer token.

    Args:
        base_url: Base URL for the Django server.
        auth_token: Bearer token sent on every request.
        timeout: Timeout in seconds for each request.
    """

    #: Base URL used to construct endpoint URLs.
    base_url: str
    #: Bearer token sent on each request.
    auth_token: str
    #: Timeout in seconds applied to outgoing requests.
    timeout: float

    def __init__(
        self,
        *,
        base_url: str,
        auth_token: str,
        timeout: float = 10.0,
    ) -> None:
        """Initialize a JSON API client.

        Keyword Args:
            base_url: Base URL for the Django server.
            auth_token: Bearer token sent on each request.
            timeout: Timeout in seconds for each request.
        """

        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout

    def get(self, path: str) -> ApiResponse:
        """Issue a GET request.

        Args:
            path: API path relative to the configured base URL.

        Returns:
            The decoded API response.
        """

        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> ApiResponse:
        """Issue a POST request with a JSON body.

        Args:
            path: API path relative to the configured base URL.
            payload: JSON payload to submit.

        Returns:
            The decoded API response.
        """

        return self.request("POST", path, payload=payload)

    def patch(self, path: str, payload: dict[str, Any]) -> ApiResponse:
        """Issue a PATCH request with a JSON body.

        Args:
            path: API path relative to the configured base URL.
            payload: JSON payload to submit.

        Returns:
            The decoded API response.
        """

        return self.request("PATCH", path, payload=payload)

    def delete(self, path: str) -> ApiResponse:
        """Issue a DELETE request.

        Args:
            path: API path relative to the configured base URL.

        Returns:
            The decoded API response.
        """

        return self.request("DELETE", path)

    def request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> ApiResponse:
        """Send a JSON request to the API.

        Args:
            method: HTTP method to use.
            path: API path relative to the configured base URL.

        Keyword Args:
            payload: Optional JSON payload for write requests.

        Raises:
            SystemExit: Raised when the request fails or the server is
                unreachable.

        Returns:
            The decoded API response.
        """

        url = urllib.parse.urljoin(f"{self.base_url}/", path.lstrip("/"))
        body = None
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            url=url,
            data=body,
            method=method,
            headers=self._build_headers(),
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return ApiResponse(
                    status_code=response.status,
                    data=self._decode_response(response.read()),
                )
        except urllib.error.HTTPError as error:
            data = self._decode_response(error.read())
            return ApiResponse(status_code=error.code, data=data)
        except urllib.error.URLError as error:
            raise SystemExit(
                f"Request to {url} failed. Is the Django server running? {error.reason}"
            ) from error

    def _build_headers(self) -> dict[str, str]:
        """Build request headers for API calls.

        Returns:
            Base JSON headers plus the required bearer token.
        """

        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
        }

    @staticmethod
    def _decode_response(body: bytes) -> Any:
        """Decode a response body into JSON when possible.

        Args:
            body: Raw response body bytes.

        Returns:
            Parsed JSON data, decoded text, or `None` for empty bodies.
        """

        if not body:
            return None

        text = body.decode("utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text


def print_step(title: str) -> None:
    """Print a human-friendly step banner.

    Args:
        title: Description of the scenario step.
    """

    print(f"\n== {title} ==")


def print_response(
    label: str,
    response: ApiResponse,
    *,
    fields: list[str] | None = None,
) -> None:
    """Print the status code and selected response fields.

    Args:
        label: Human-readable request label.
        response: Response to summarize.

    Keyword Args:
        fields: Optional top-level field names to print from JSON payloads.
    """

    print(f"{label}: HTTP {response.status_code}")
    if fields and isinstance(response.data, dict):
        for field in fields:
            if field in response.data:
                print(f"  {field}: {response.data[field]}")
    elif response.data is not None and not isinstance(response.data, dict):
        print(f"  body: {response.data}")


def expect_status(
    response: ApiResponse,
    expected_statuses: set[int],
    *,
    action: str,
) -> None:
    """Exit loudly when a response has an unexpected status.

    Args:
        response: Response to validate.
        expected_statuses: Acceptable HTTP status codes.

    Keyword Args:
        action: Description of the failing step.

    Raises:
        SystemExit: Raised when the response status is unexpected.
    """

    if response.status_code not in expected_statuses:
        raise SystemExit(
            f"{action} failed with HTTP {response.status_code}: {response.data}"
        )


def build_author_payloads(run_label: str) -> list[dict[str, str]]:
    """Build author payloads unique to this run.

    Args:
        run_label: Short label used to keep test records distinguishable.

    Returns:
        Two author payloads ready for POST requests.
    """

    return [
        {
            "first_name": "Octavia",
            "last_name": f"Butler {run_label}",
            "middle_name": "E.",
            "full_name": f"Octavia E. Butler {run_label}",
        },
        {
            "first_name": "Nnedi",
            "last_name": f"Okorafor {run_label}",
            "middle_name": "",
            "full_name": f"Nnedi Okorafor {run_label}",
        },
    ]


def cleanup_records(
    client: ApiClient,
    *,
    book_id: int | None,
    author_ids: list[int],
) -> None:
    """Delete created records in reverse dependency order.

    Side Effects:
        Sends DELETE requests to the API.

    Keyword Args:
        client: API client used to issue requests.
        book_id: Created book ID, if any.
        author_ids: Created author IDs.
    """

    print_step("Cleanup")
    if book_id is not None:
        response = client.delete(f"/api/books/{book_id}/")
        print_response("Delete book", response)
        expect_status(response, {204}, action="Book cleanup")
    for author_id in author_ids:
        response = client.delete(f"/api/authors/{author_id}/")
        print_response(f"Delete author {author_id}", response)
        expect_status(response, {204}, action=f"Author cleanup for {author_id}")


def run_scenario(*, client: ApiClient, cleanup: bool) -> None:
    """Run the end-to-end API smoke test flow.

    Side Effects:
        Creates, updates, fetches, and optionally deletes API records.

    Keyword Args:
        client: API client used for all requests.
        cleanup: Whether to delete created records at the end.
    """

    run_label = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    author_payloads = build_author_payloads(run_label)
    author_ids: list[int] = []
    book_id: int | None = None

    try:
        print_step("Create authors")
        for index, payload in enumerate(author_payloads, start=1):
            response = client.post("/api/authors/", payload)
            print_response(
                f"Create author {index}",
                response,
                fields=["id", "full_name"],
            )
            expect_status(response, {201}, action=f"Create author {index}")
            assert isinstance(response.data, dict)
            author_ids.append(int(response.data["id"]))

        print_step("Create book")
        create_book_response = client.post(
            "/api/books/",
            {
                "title": f"API Smoke Book {run_label}",
                "isbn": run_label[-10:],
                "authors": [
                    {"author_id": author_ids[0], "order": 1},
                    {"author_id": author_ids[1], "order": 2},
                ],
            },
        )
        print_response(
            "Create book",
            create_book_response,
            fields=["id", "title", "slug"],
        )
        expect_status(create_book_response, {201}, action="Create book")
        assert isinstance(create_book_response.data, dict)
        book_id = int(create_book_response.data["id"])

        print_step("Fetch created book")
        fetch_book_response = client.get(f"/api/books/{book_id}/")
        print_response(
            "Fetch book",
            fetch_book_response,
            fields=["id", "title", "slug"],
        )
        expect_status(fetch_book_response, {200}, action="Fetch book")
        if isinstance(fetch_book_response.data, dict):
            authors = fetch_book_response.data.get("authors", [])
            print(f"  authors: {authors}")

        print_step("Update book metadata and author order")
        update_book_response = client.patch(
            f"/api/books/{book_id}/",
            {
                "title": f"API Smoke Book {run_label} Updated",
                "authors": [
                    {"author_id": author_ids[1], "order": 1},
                    {"author_id": author_ids[0], "order": 2},
                ],
            },
        )
        print_response(
            "Patch book",
            update_book_response,
            fields=["id", "title", "slug"],
        )
        expect_status(update_book_response, {200}, action="Patch book")
        if isinstance(update_book_response.data, dict):
            authors = update_book_response.data.get("authors", [])
            print(f"  authors: {authors}")

        print_step("Confirm updated book")
        confirm_book_response = client.get(f"/api/books/{book_id}/")
        print_response(
            "Re-fetch book",
            confirm_book_response,
            fields=["id", "title", "slug"],
        )
        expect_status(confirm_book_response, {200}, action="Re-fetch book")
        if isinstance(confirm_book_response.data, dict):
            authors = confirm_book_response.data.get("authors", [])
            print(f"  authors: {authors}")

        if cleanup:
            cleanup_records(client, book_id=book_id, author_ids=author_ids)
            book_id = None
            author_ids.clear()
        else:
            print_step("Cleanup skipped")
            print(f"Created author IDs: {author_ids}")
            print(f"Created book ID: {book_id}")
            print("Re-run with --cleanup to delete created records automatically.")

        print("\nScenario completed successfully.")
    finally:
        if cleanup and (book_id is not None or author_ids):
            cleanup_records(client, book_id=book_id, author_ids=author_ids)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the smoke test.

    Returns:
        Parsed command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description="Exercise the local /api/ author and book endpoints."
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base URL for the Django server. Defaults to {DEFAULT_BASE_URL}.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the created book and authors after the scenario succeeds.",
    )
    parser.add_argument(
        "--auth-token",
        required=True,
        help="Bearer token used for every API request.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-request timeout in seconds.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the CLI entry point.

    Returns:
        Process exit code.
    """

    args = parse_args()
    client = ApiClient(
        base_url=args.base_url,
        auth_token=args.auth_token,
        timeout=args.timeout,
    )
    run_scenario(client=client, cleanup=args.cleanup)
    return 0


if __name__ == "__main__":
    sys.exit(main())
