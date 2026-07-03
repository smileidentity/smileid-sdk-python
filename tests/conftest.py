"""Shared test fixtures and helpers.

All HTTP is mocked with respx; no real network calls are made. Golden values
follow (fake IDs, partner id 1234, john@example.com).
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Dict, List

import httpx
import pytest

import usesmileid

BASE_URL = "https://testapi.smileidentity.com"

# A tiny valid JPEG-ish byte string and PNG magic for binary tests.
JPEG_BYTES = b"\xff\xd8\xff\xe0stub-jpeg"
LIVENESS = [b"live-%d" % i for i in range(6)]


def make_jwt(exp_offset: int = 3600) -> str:
    """Build a fake JWT whose exp claim is ``now + exp_offset`` seconds."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    claims = json.dumps({"exp": int(time.time()) + exp_offset}).encode()
    payload = base64.urlsafe_b64encode(claims).rstrip(b"=").decode()
    return f"{header}.{payload}.signature"


def make_client(**overrides: Any) -> usesmileid.Client:
    kwargs: Dict[str, Any] = {
        "partner_id": "1234",
        "api_key": "test-api-key",
        "environment": "sandbox",
    }
    kwargs.update(overrides)
    return usesmileid.Client(**kwargs)


def parse_multipart(request: httpx.Request) -> List[Dict[str, Any]]:
    """Parse a multipart request body into a list of part descriptors."""
    content_type = request.headers["content-type"]
    assert content_type.startswith("multipart/form-data"), content_type
    boundary = content_type.split("boundary=")[1].strip()
    separator = ("--" + boundary).encode()
    parts: List[Dict[str, Any]] = []
    for chunk in request.content.split(separator):
        chunk = chunk.strip(b"\r\n")
        if not chunk or chunk == b"--":
            continue
        head, _, body = chunk.partition(b"\r\n\r\n")
        name = filename = ctype = None
        for line in head.decode().split("\r\n"):
            lower = line.lower()
            if lower.startswith("content-disposition"):
                for segment in line.split(";"):
                    segment = segment.strip()
                    if segment.startswith("name="):
                        name = segment[5:].strip('"')
                    elif segment.startswith("filename="):
                        filename = segment[9:].strip('"')
            elif lower.startswith("content-type"):
                ctype = line.split(":", 1)[1].strip()
        parts.append(
            {"name": name, "filename": filename, "content_type": ctype, "body": body}
        )
    return parts


def part_names(parts: List[Dict[str, Any]]) -> List[str]:
    return [p["name"] for p in parts]


def consent_dict() -> dict:
    return {
        "granted": True,
        "granted_at": "2026-03-06T12:00:00.000Z",
        "notice_language": "EN",
        "notice_privacy_policy_url": "https://example.com/privacy",
    }


def user_details_dict() -> dict:
    return {"given_names": "John", "last_name": "Doe", "email": "john@example.com"}


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make retry backoff instantaneous so retry tests run fast."""
    monkeypatch.setattr("usesmileid.client.transport.time.sleep", lambda *_a, **_k: None)


@pytest.fixture
def mock_token(respx_mock: Any) -> Any:
    """Register the /v3/token route returning a long-lived JWT."""
    return respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": make_jwt()})
    )
