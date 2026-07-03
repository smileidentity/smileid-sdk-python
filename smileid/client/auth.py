"""JWT token lifecycle."""

from __future__ import annotations

import base64
import json
import threading
import time
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
