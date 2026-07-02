"""Consent builder (spec §5.1).

Serialized as a JSON part named ``consent``. ``granted`` is always ``true`` — the
wire schema permits no other value.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Union


def _to_iso8601(value: Union[str, datetime]) -> str:
    if isinstance(value, datetime):
        moment = value.astimezone(timezone.utc)
        return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"
    return value


class Consent:
    """A granted-consent record. Build via :meth:`granted`."""

    def __init__(
        self,
        granted_at: Union[str, datetime],
        notice_language: str,
        notice_privacy_policy_url: str,
    ) -> None:
        self.granted_at = _to_iso8601(granted_at)
        self.notice_language = notice_language
        self.notice_privacy_policy_url = notice_privacy_policy_url

    @classmethod
    def granted(
        cls,
        *,
        granted_at: Union[str, datetime],
        notice_language: str,
        notice_privacy_policy_url: str,
    ) -> "Consent":
        """Build a consent record with ``granted=true`` (spec §5.1)."""
        return cls(granted_at, notice_language, notice_privacy_policy_url)

    def to_dict(self) -> dict:
        return {
            "granted": True,
            "granted_at": self.granted_at,
            "notice_language": self.notice_language,
            "notice_privacy_policy_url": self.notice_privacy_policy_url,
        }
