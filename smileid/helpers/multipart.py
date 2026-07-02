"""Binary input normalization for multipart parts.

Binary inputs accept a file path, a bytes buffer, or a file-like object, and are
normalized to ``(filename, bytes, content_type)`` tuples.

Content-type policy: ``selfie_image``, ``liveness_images`` and
``comparison_image`` are always ``image/jpeg``. Only ``document`` and
``document_back`` may be ``image/png``, detected from the PNG magic bytes or a
``.png`` file extension (pass ``allow_png=True``).
"""

from __future__ import annotations

import os
from typing import Any, List, Optional, Tuple

from smileid.errors import ValidationError

BinaryPart = Tuple[str, bytes, str]

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG = "image/jpeg"


def _content_type(filename: str, data: bytes, allow_png: bool) -> str:
    if allow_png and (data.startswith(_PNG_MAGIC) or filename.lower().endswith(".png")):
        return "image/png"
    return _JPEG


def normalize_binary(
    value: Any,
    *,
    default_filename: str,
    allow_png: bool = False,
) -> Optional[BinaryPart]:
    """Normalize one binary input to ``(filename, bytes, content_type)``.

    Returns ``None`` when ``value`` is ``None``. PNG detection runs only when
    ``allow_png`` is true (document and document_back).
    """
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        data = bytes(value)
        return (default_filename, data, _content_type(default_filename, data, allow_png))
    if isinstance(value, (str, os.PathLike)):
        path = os.fspath(value)
        with open(path, "rb") as handle:
            data = handle.read()
        filename = os.path.basename(path) or default_filename
        return (filename, data, _content_type(filename, data, allow_png))
    if hasattr(value, "read"):
        raw = value.read()
        data = raw.encode("utf-8") if isinstance(raw, str) else bytes(raw)
        name = getattr(value, "name", None)
        filename = os.path.basename(name) if isinstance(name, str) else default_filename
        return (filename, data, _content_type(filename, data, allow_png))
    raise ValidationError(
        "binary input must be a file path, bytes, or a file-like object"
    )


def normalize_binary_list(
    values: Any,
    *,
    prefix: str,
) -> Optional[List[BinaryPart]]:
    """Normalize a list of binary inputs (e.g. liveness_images). Always JPEG."""
    if values is None:
        return None
    parts: List[BinaryPart] = []
    for index, value in enumerate(values):
        part = normalize_binary(value, default_filename=f"{prefix}_{index}.jpg")
        if part is not None:
            parts.append(part)
    return parts
