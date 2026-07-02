"""Fraud-report validation (spec §6.11)."""

from __future__ import annotations

from typing import Optional

from smileid.errors import ValidationError

FRAUD_REASONS = frozenset(
    {
        "FIRST_PARTY_FRAUD",
        "SECOND_PARTY_FRAUD",
        "THIRD_PARTY_FRAUD",
        "SYNTHETIC_IDENTITY",
        "ACCOUNT_TAKEOVER",
        "DOCUMENT_FORGERY",
        "IDENTITY_FARMING",
        "MULE_ACCOUNT",
        "OTHER",
    }
)

_MAX_NOTES_LENGTH = 500


def validate_fraud_report(
    *,
    is_fraud: bool,
    reason: Optional[str],
    notes: Optional[str],
) -> None:
    """Enforce the conditional fraud-report rules before sending (spec §6.11).

    - ``reason`` is required and must be a known value when ``is_fraud`` is true.
    - ``notes`` is required when ``is_fraud`` is false OR when ``reason`` is
      ``OTHER``; it must be at most 500 characters.
    """
    if is_fraud:
        if not reason:
            raise ValidationError("reason is required when is_fraud is true")
        if reason not in FRAUD_REASONS:
            raise ValidationError(
                f"reason must be one of {sorted(FRAUD_REASONS)}, got {reason!r}"
            )
        if reason == "OTHER" and not notes:
            raise ValidationError("notes is required when reason is OTHER")
    else:
        if not notes:
            raise ValidationError("notes is required when is_fraud is false")

    if notes is not None and len(notes) > _MAX_NOTES_LENGTH:
        raise ValidationError(
            f"notes must be at most {_MAX_NOTES_LENGTH} characters"
        )
