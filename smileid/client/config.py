"""Client configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from smileid.errors import ValidationError

Environment = str  # "sandbox" | "production"

_BASE_URLS = {
    "sandbox": "https://testapi.smileidentity.com",
    "production": "https://api.smileidentity.com",
}

_PARTNER_ID_RE = re.compile(r"^[1-9]\d*$")


@dataclass
class ClientConfig:
    """Resolved, validated client configuration.

    ``base_url`` is derived from ``environment`` unless overridden explicitly.
    """

    partner_id: str
    api_key: str
    environment: Environment = "sandbox"
    partner_secret: Optional[str] = None
    default_callback_url: Optional[str] = None
    base_url: Optional[str] = None
    allow_insecure_base_url: bool = False
    timeout: float = 30.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        if not self.partner_id or not _PARTNER_ID_RE.match(self.partner_id):
            raise ValidationError(
                "partner_id must be a numeric string with no leading zeros"
            )
        if not self.api_key:
            raise ValidationError("api_key is required")
        if self.environment not in _BASE_URLS:
            raise ValidationError(
                f"environment must be one of {sorted(_BASE_URLS)}, got {self.environment!r}"
            )
        if self.base_url is None:
            self.base_url = _BASE_URLS[self.environment]
        self.base_url = _normalize_base_url(
            self.base_url, allow_insecure=self.allow_insecure_base_url
        )
        if self.default_callback_url:
            validate_callback_url(self.default_callback_url)

    @property
    def signing_enabled(self) -> bool:
        """HMAC signing is enabled only when a partner_secret is configured."""
        return bool(self.partner_secret)


def validate_callback_url(value: str) -> None:
    parsed = urlparse(value.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValidationError("callback_url must be an absolute URL")
    if parsed.scheme != "https":
        raise ValidationError("callback_url must use https")


def _normalize_base_url(value: str, *, allow_insecure: bool) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValidationError("base_url must be an absolute URL")
    if parsed.query or parsed.fragment:
        raise ValidationError("base_url must not include query or fragment")
    if parsed.scheme == "https":
        return value
    if allow_insecure and parsed.scheme == "http" and _is_loopback_host(parsed.hostname):
        return value
    raise ValidationError("base_url must use https")


def _is_loopback_host(host: Optional[str]) -> bool:
    return bool(host == "localhost" or host == "::1" or (host and host.startswith("127.")))
