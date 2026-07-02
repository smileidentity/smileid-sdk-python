"""HMAC request signing: wired but OFF unless partner_secret is set."""

from __future__ import annotations

import hashlib
import hmac
import re
from typing import Any

import httpx

from tests.conftest import BASE_URL, consent_dict, make_client, user_details_dict

ACCEPTED = {"status": "Accepted", "job_id": "job_x", "user_id": "user_x"}


def _verify(client: Any) -> Any:
    return client.enhanced_kyc.verify(
        country="NG",
        id_type="NIN",
        id_number="12345678901",
        user_details=user_details_dict(),
        consent=consent_dict(),
    )


def test_no_signing_headers_without_partner_secret(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    client = make_client()
    _verify(client)
    request = route.calls.last.request
    assert "SmileID-Timestamp" not in request.headers
    assert "SmileID-Request-Signature" not in request.headers


def test_signing_headers_present_and_correct_with_partner_secret(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    secret = "test-partner-secret"
    client = make_client(partner_secret=secret)
    _verify(client)
    request = route.calls.last.request

    timestamp = request.headers["SmileID-Timestamp"]
    signature = request.headers["SmileID-Request-Signature"]

    # ISO 8601 UTC with milliseconds, e.g. 2026-03-10T12:00:00.000Z.
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", timestamp)

    # Signature covers the exact serialized body bytes as sent.
    expected = hmac.new(
        secret.encode(), timestamp.encode() + request.content, hashlib.sha256
    ).hexdigest()
    assert signature == expected
