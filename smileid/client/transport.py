"""HTTP transport.

The single layer that touches HTTP: it builds the URL, attaches auth and
telemetry headers, optionally signs the body, serializes the multipart / JSON
body, applies the retry policy, and raises a typed error on failure.
"""

from __future__ import annotations

import platform
import random
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional, Tuple

import httpx

from smileid._version import __version__
from smileid.client.auth import TokenManager
from smileid.client.config import ClientConfig
from smileid.errors import (
    ConnectionError,
    UnexpectedResponseError,
    ValidationError,
    parse_error,
    parse_success_json,
)
from smileid.generated import operations
from smileid.generated.operations import Request

# HTTP statuses that are safe to retry for idempotent operations.
# 409 is deliberately absent — it is a business-state conflict, not transient.
_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

# Upper bound on a server-provided Retry-After delay, in seconds.
_MAX_RETRY_AFTER_SECONDS = 60.0


class Transport:
    def __init__(
        self,
        config: ClientConfig,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._config = config
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(timeout=config.timeout)
        self.token_manager = TokenManager(self._fetch_token)
        # Base backoff in seconds; tests patch ``time.sleep`` to keep fast.
        self._backoff_base = 0.5

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    # -- headers -----------------------------------------------------------

    def _telemetry_headers(self) -> dict:
        return {
            "SmileID-Source-SDK": "python",
            "SmileID-Source-SDK-Version": __version__,
            "User-Agent": (
                f"smileid-sdk-python/{__version__} "
                f"(python/{platform.python_version()})"
            ),
        }

    # -- token -------------------------------------------------------------

    def _fetch_token(self) -> str:
        request = operations.token(self._config.partner_id, self._config.api_key)
        response = self._send_with_retries(request, timeout=None)
        if response.status_code != 200:
            raise parse_error(response)
        body = parse_success_json(response)
        token = body.get("token")
        if not isinstance(token, str) or not token:
            raise UnexpectedResponseError(
                "token response did not contain a 'token' field",
                status_code=response.status_code,
                raw_body=response.text,
            )
        return token

    # -- public send -------------------------------------------------------

    def send(self, request: Request, *, timeout: Optional[float] = None) -> httpx.Response:
        """Execute a request, refreshing the token once on a 401."""
        response: Optional[httpx.Response] = None
        for auth_attempt in range(2):
            response = self._send_with_retries(request, timeout=timeout)
            if response.status_code == 401 and request.authenticated and auth_attempt == 0:
                self.token_manager.invalidate()
                continue
            break
        assert response is not None
        if response.status_code in request.ok_statuses:
            return response
        raise parse_error(response)

    # -- retry loop --------------------------------------------------------

    def _send_with_retries(
        self, request: Request, *, timeout: Optional[float]
    ) -> httpx.Response:
        attempts = self._config.max_retries + 1 if request.idempotent else 1
        response: Optional[httpx.Response] = None
        for attempt in range(attempts):
            prepared = self._prepare(request, timeout)
            try:
                response = self._client.send(prepared)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if request.idempotent and attempt < attempts - 1:
                    time.sleep(self._backoff(attempt))
                    continue
                raise ConnectionError(str(exc)) from exc

            if response.status_code in request.ok_statuses:
                return response
            if response.status_code == 401:
                return response  # send() decides whether to refresh
            if (
                request.idempotent
                and attempt < attempts - 1
                and response.status_code in _RETRYABLE_STATUSES
            ):
                delay = self._retry_after(response)
                time.sleep(delay if delay is not None else self._backoff(attempt))
                continue
            return response
        assert response is not None
        return response

    def _backoff(self, attempt: int) -> float:
        return self._backoff_base * (2 ** attempt) + random.uniform(0, self._backoff_base)

    @staticmethod
    def _retry_after(response: httpx.Response) -> Optional[float]:
        """Parse Retry-After: delta-seconds or an RFC 7231 HTTP-date.

        The result is floored at 0 and capped at 60 seconds so a
        server-provided value can never stall the client indefinitely.
        """
        value = response.headers.get("retry-after")
        if not value:
            return None
        try:
            delay = float(value)
        except ValueError:
            try:
                moment = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return None
            if moment is None:
                return None
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=timezone.utc)
            delay = (moment - datetime.now(timezone.utc)).total_seconds()
        return min(max(delay, 0.0), _MAX_RETRY_AFTER_SECONDS)

    # -- request assembly --------------------------------------------------

    def _prepare(self, request: Request, timeout: Optional[float]) -> httpx.Request:
        headers = self._telemetry_headers()
        if request.authenticated:
            headers["SmileID-Token"] = self.token_manager.ensure_token()
        if request.needs_partner_id_header:
            headers["SmileID-Partner-ID"] = self._config.partner_id
        if request.user_id_header is not None:
            headers["User-ID"] = request.user_id_header
        headers.update(request.extra_headers)

        url = f"{self._config.base_url}{request.path}"
        per_request_timeout = timeout if timeout is not None else self._config.timeout

        build_kwargs: dict = {
            "params": request.query or None,
            "headers": headers,
            "timeout": per_request_timeout,
        }
        if request.body_kind == "multipart":
            build_kwargs["files"] = self._multipart_files(request)
        elif request.body_kind == "json" and request.json_body is not None:
            build_kwargs["json"] = request.json_body

        return self._client.build_request(request.method, url, **build_kwargs)

    @staticmethod
    def _multipart_files(request: Request) -> List[Tuple[str, tuple]]:
        """Assemble multipart parts.

        Every part is routed through httpx's ``files`` list so the body is
        always ``multipart/form-data`` (even scalar-only bodies), part order is
        preserved, and repeated ``liveness_images`` stay as separate parts.
        Filenames and content types are sanitized against header injection.
        """
        files: List[Tuple[str, tuple]] = []
        for name, value in request.text_parts:
            files.append((name, (None, value.encode("utf-8"), None)))
        for name, json_text in request.json_parts:
            files.append((name, (None, json_text.encode("utf-8"), "application/json")))
        for name, filename, data, content_type in request.binary_parts:
            files.append(
                (name, (_sanitize_filename(filename), data, _check_media_type(content_type)))
            )
        return files


# Conservative allow-list for multipart part headers: a filename must not be
# able to break out of its Content-Disposition parameter, and a content type
# must be a plain media type. Defense in depth — content types are derived
# internally today, and httpx additionally escapes filenames.
_FILENAME_UNSAFE_RE = re.compile(r'[\r\n"\\;]')
_MEDIA_TYPE_RE = re.compile(r"^[!#$&^_.+\-\w]+/[!#$&^_.+\-\w]+$")


def _sanitize_filename(filename: str) -> str:
    """Strip CR/LF, quotes, backslashes and separators from a part filename."""
    cleaned = _FILENAME_UNSAFE_RE.sub("_", filename)
    return cleaned or "upload"


def _check_media_type(content_type: str) -> str:
    """Reject any part content type that is not a plain media type."""
    if not _MEDIA_TYPE_RE.match(content_type):
        raise ValidationError(f"invalid part content type: {content_type!r}")
    return content_type
