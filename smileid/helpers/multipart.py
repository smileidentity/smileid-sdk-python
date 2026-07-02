"""Binary input normalization for multipart parts (spec §5.3, §8).

Binary inputs accept a file path, a bytes buffer, or a file-like object, and are
normalized to ``(filename, bytes, content_type)`` tuples.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional, Tuple

from smileid.errors import ValidationError

BinaryPart = Tuple[str, bytes, str]

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _content_type(filename: str, data: bytes, default: str) -> str:
    if data.startswith(_PNG_MAGIC) or filename.lower().endswith(".png"):
        return "image/png"
    return default


def normalize_binary(
    value: Any,
    *,
    default_filename: str,
    content_type: str = "image/jpeg",
) -> Optional[BinaryPart]:
    """Normalize one binary input to ``(filename, bytes, content_type)``.

    Returns ``None`` when ``value`` is ``None``.
    """
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        data = bytes(value)
        return (default_filename, data, _content_type(default_filename, data, content_type))
    if isinstance(value, (str, os.PathLike)):
        path = os.fspath(value)
        with open(path, "rb") as handle:
            data = handle.read()
        filename = os.path.basename(path) or default_filename
        return (filename, data, _content_type(filename, data, content_type))
    if hasattr(value, "read"):
        raw = value.read()
        data = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        name = getattr(value, "name", None)
        filename = os.path.basename(name) if isinstance(name, str) else default_filename
        return (filename, data, _content_type(filename, data, content_type))
    raise ValidationError(
        "binary input must be a file path, bytes, or a file-like object"
    )


def normalize_binary_list(
    values: Any,
    *,
    prefix: str,
    content_type: str = "image/jpeg",
) -> Optional[List[BinaryPart]]:
    """Normalize a list of binary inputs (e.g. liveness_images)."""
    if values is None:
        return None
    parts: List[BinaryPart] = []
    for index, value in enumerate(values):
        part = normalize_binary(
            value, default_filename=f"{prefix}_{index}.jpg", content_type=content_type
        )
        if part is not None:
            parts.append(part)
    return parts
