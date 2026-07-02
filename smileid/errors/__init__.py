"""Typed error hierarchy for the Smile ID SDK (spec §7).

One base class, ``SmileIDError``; typed subclasses keyed on HTTP status. Every
error exposes ``status_code``, ``status`` (HTTP status text from the body when
present), ``message``, ``code`` (present only on the services ``{error, code}``
shape), ``request_id`` and ``raw_body``.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import httpx

__all__ = [
    "SmileIDError",
    "InvalidRequestError",
    "ValidationError",
    "AuthenticationError",
    "PaymentRequiredError",
    "PermissionError",
    "NotFoundError",
    "ConflictError",
    "PayloadTooLargeError",
    "RateLimitError",
    "APIError",
    "ConnectionError",
    "TimeoutError",
    "error_class_for",
    "parse_error",
]


class SmileIDError(Exception):
    """Base class for every error raised by the SDK."""

    def __init__(
        self,
        message: Optional[str] = None,
        *,
        status_code: Optional[int] = None,
        status: Optional[str] = None,
        code: Optional[str] = None,
        request_id: Optional[str] = None,
        raw_body: Optional[str] = None,
    ) -> None:
        super().__init__(message or "")
        self.message = message
        self.status_code = status_code
        self.status = status
        self.code = code
        self.request_id = request_id
        self.raw_body = raw_body


class InvalidRequestError(SmileIDError):
    """HTTP 400 / 415 — malformed or unsupported request."""


class ValidationError(InvalidRequestError):
    """Client-side validation failure, raised before any request is sent."""


class AuthenticationError(SmileIDError):
    """HTTP 401 — invalid or missing credentials / token."""


class PaymentRequiredError(SmileIDError):
    """HTTP 402 — insufficient wallet balance."""


class PermissionError(SmileIDError):  # noqa: A001 - intentional public name
    """HTTP 403 — caller is not authorised for the operation."""


class NotFoundError(SmileIDError):
    """HTTP 404 — resource not found (not raised by verifications.retrieve)."""


class ConflictError(SmileIDError):
    """HTTP 409 — business-state conflict (e.g. replay still processing)."""


class PayloadTooLargeError(SmileIDError):
    """HTTP 413 — request payload too large."""


class RateLimitError(SmileIDError):
    """HTTP 429 — too many requests."""


class APIError(SmileIDError):
    """HTTP 5xx — server-side error."""


class ConnectionError(SmileIDError):  # noqa: A001 - intentional public name
    """Network failure or timeout with no HTTP response."""


class TimeoutError(SmileIDError):  # noqa: A001 - intentional public name
    """SDK-local timeout, raised by ``wait_until_complete``."""


_STATUS_MAP = {
    400: InvalidRequestError,
    415: InvalidRequestError,
    401: AuthenticationError,
    402: PaymentRequiredError,
    403: PermissionError,
    404: NotFoundError,
    409: ConflictError,
    413: PayloadTooLargeError,
    429: RateLimitError,
}


def error_class_for(status_code: int) -> type[SmileIDError]:
    """Return the error class for an HTTP status code (spec §7 table)."""
    klass = _STATUS_MAP.get(status_code)
    if klass is not None:
        return klass
    if status_code >= 500:
        return APIError
    return SmileIDError


def parse_error(response: "httpx.Response") -> SmileIDError:
    """Build a typed error from a failed HTTP response (spec §2A parse_error).

    Handles both wire shapes: ``{status, message}`` (everywhere; id_status
    reorders to ``{message, status}``) and ``{error, code}`` (the three
    unauthenticated services endpoints). The class is chosen by HTTP status,
    never by body contents.
    """
    raw_body = response.text
    body: dict[str, Any] = {}
    try:
        parsed = json.loads(raw_body)
        if isinstance(parsed, dict):
            body = parsed
    except (ValueError, TypeError):
        body = {}

    message = body.get("message") or body.get("error") or response.reason_phrase
    code = body.get("code")
    status_text = body.get("status")
    request_id = response.headers.get("x-request-id") or response.headers.get(
        "smileid-request-id"
    )

    klass = error_class_for(response.status_code)
    return klass(
        message,
        status_code=response.status_code,
        status=status_text,
        code=code,
        request_id=request_id,
        raw_body=raw_body,
    )
