"""Client configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from usesmileid.errors import ValidationError

Environment = str  # "sandbox" | "production"

_BASE_URLS = {
    "sandbox": "https://testapi.smileidentity.com",
    "production": "https://api.smileidentity.com",
}

_PARTNER_ID_RE = re.compile(r"^[1-9]\d*$")


def validate_base_url(value: str) -> None:
    """Require an absolute https URL with no query or fragment.

    Deliberately strict, with no insecure escape hatch: partner credentials
    and PII travel on every request.
    """
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValidationError(f"base_url must be an absolute https URL, got {value!r}")
    if parsed.query or parsed.fragment:
        raise ValidationError(f"base_url must not contain a query or fragment, got {value!r}")


def validate_callback_url(value: str) -> None:
    """Require callback URLs to be absolute https URLs."""
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValidationError(f"callback_url must be an absolute https URL, got {value!r}")


@dataclass
class ClientConfig:
    """Resolved, validated client configuration.

    ``base_url`` is derived from ``environment`` unless overridden explicitly.
    """

    partner_id: str
    api_key: str
    environment: Environment = "sandbox"
    default_callback_url: Optional[str] = None
    base_url: Optional[str] = None
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
        validate_base_url(self.base_url)
        self.base_url = self.base_url.rstrip("/")
        if self.default_callback_url is not None:
            validate_callback_url(self.default_callback_url)
