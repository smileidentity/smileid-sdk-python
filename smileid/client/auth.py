"""JWT token lifecycle and the HMAC signing hook."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional

# Refresh a token this many seconds before its ``exp`` claim.
_EXPIRY_SKEW_SECONDS = 60


def decode_jwt_exp(jwt: str) -> Optional[int]:
    """Return the ``exp`` claim (epoch seconds) from a JWT, or ``None``.

    The token response carries no explicit expiry, so the ``exp`` claim is the
    only signal. Returns ``None`` when the token cannot be decoded.
    """
    try:
        payload_segment = jwt.split(".")[1]
        padding = "=" * (-len(payload_segment) % 4)
        decoded = base64.urlsafe_b64decode(payload_segment + padding)
        claims = json.loads(decoded)
        exp = claims.get("exp")
        return int(exp) if exp is not None else None
    except (ValueError, IndexError, TypeError, json.JSONDecodeError):
        return None


class TokenManager:
    """Thread-safe cache for the internal JWT.

    Concurrent callers never stampede the token endpoint: fetching happens under
    a lock. Callers pass a ``fetcher`` that performs the actual POST /v3/token.
    """

    def __init__(self, fetcher: Callable[[], str]) -> None:
        self._fetcher = fetcher
        self._lock = threading.Lock()
        self._jwt: Optional[str] = None
        self._expires_at: float = 0.0

    def ensure_token(self) -> str:
        """Return a valid cached token, fetching a fresh one when needed."""
        with self._lock:
            if self._jwt is not None and time.time() < self._expires_at:
                return self._jwt
            jwt = self._fetcher()
            exp = decode_jwt_exp(jwt)
            self._jwt = jwt
            # A decodable exp gives a real cache window; otherwise treat the
            # token as single-use and refresh on the next call.
            self._expires_at = (exp - _EXPIRY_SKEW_SECONDS) if exp is not None else 0.0
            return jwt

    def invalidate(self) -> None:
        """Drop the cached token so the next call fetches a fresh one."""
        with self._lock:
            self._jwt = None
            self._expires_at = 0.0


def iso8601_millis_utc(moment: Optional[datetime] = None) -> str:
    """Format a UTC timestamp as ISO 8601 with milliseconds, e.g.
    ``2026-03-10T12:00:00.000Z``."""
    moment = (moment or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def sign_request(partner_secret: str, timestamp: str, body: bytes) -> str:
    """Compute the provisional HMAC request signature.

    ``hex(HMAC_SHA256(key=partner_secret, message=timestamp + body_bytes))``.

    Provisional construction — must be confirmed with the backend before it is
    enabled in production.
    """
    message = timestamp.encode("utf-8") + body
    return hmac.new(
        partner_secret.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
