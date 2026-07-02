"""Client configuration."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

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
        self.base_url = self.base_url.rstrip("/")

    @property
    def signing_enabled(self) -> bool:
        """HMAC signing is enabled only when a partner_secret is configured."""
        return bool(self.partner_secret)
