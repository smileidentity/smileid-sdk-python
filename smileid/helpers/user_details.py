"""user_details model and client-side validation (spec §5.1).

At least one of ``email`` / ``phone_number`` MUST be present; enforced before a
request is sent. Serialized as a JSON part named ``user_details``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from smileid.errors import ValidationError


@dataclass
class UserDetails:
    """Consumer-stated PII (spec §5.1). Prefer passing this or a plain dict."""

    given_names: str
    last_name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None

    def to_dict(self) -> dict:
        data = {"given_names": self.given_names, "last_name": self.last_name}
        if self.email is not None:
            data["email"] = self.email
        if self.phone_number is not None:
            data["phone_number"] = self.phone_number
        return data


def normalize_user_details(value: Union["UserDetails", dict]) -> dict:
    """Validate and return the wire dict for user_details (spec §5.1).

    Raises :class:`ValidationError` when required fields are missing or when
    neither email nor phone_number is provided.
    """
    if isinstance(value, UserDetails):
        data = value.to_dict()
    elif isinstance(value, dict):
        data = dict(value)
    else:
        raise ValidationError("user_details must be a UserDetails or a dict")

    if not data.get("given_names"):
        raise ValidationError("user_details.given_names is required")
    if not data.get("last_name"):
        raise ValidationError("user_details.last_name is required")
    if not data.get("email") and not data.get("phone_number"):
        raise ValidationError(
            "user_details requires at least one of email or phone_number"
        )
    return data
