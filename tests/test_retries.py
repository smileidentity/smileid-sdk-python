"""Matrix item 3: retry policy."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

import smileid
from tests.conftest import BASE_URL, consent_dict, make_client, user_details_dict


def test_get_retried_on_500_then_succeeds(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.get(f"{BASE_URL}/v3/services/id_status").mock(
        side_effect=[
            httpx.Response(500, json={"status": "Server Error", "message": "boom"}),
            httpx.Response(200, json={"last_known_status": "online"}),
        ]
    )
    client = make_client()
    result = client.services.id_status(country="NG", id_type="NIN")
    assert result.last_known_status == "online"
    assert route.call_count == 2


def test_get_retried_on_429_and_honours_retry_after(
    respx_mock: Any, mock_token: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps = []
    monkeypatch.setattr(
        "smileid.client.transport.time.sleep", lambda s: sleeps.append(s)
    )
    route = respx_mock.get(f"{BASE_URL}/v3/services/id_status").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}, json={"status": "x", "message": "y"}),
            httpx.Response(200, json={}),
        ]
    )
    client = make_client()
    client.services.id_status(country="NG", id_type="NIN")
    assert route.call_count == 2
    assert sleeps == [7.0]  # honoured Retry-After header


def test_retry_after_http_date_form(
    respx_mock: Any, mock_token: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RFC 7231 HTTP-date Retry-After is parsed into a relative delay."""
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    sleeps = []
    monkeypatch.setattr(
        "smileid.client.transport.time.sleep", lambda s: sleeps.append(s)
    )
    retry_at = format_datetime(
        datetime.now(timezone.utc) + timedelta(seconds=10), usegmt=True
    )
    route = respx_mock.get(f"{BASE_URL}/v3/services/id_status").mock(
        side_effect=[
            httpx.Response(
                429, headers={"Retry-After": retry_at}, json={"status": "x", "message": "y"}
            ),
            httpx.Response(200, json={}),
        ]
    )
    client = make_client()
    client.services.id_status(country="NG", id_type="NIN")
    assert route.call_count == 2
    assert len(sleeps) == 1
    assert 8.0 <= sleeps[0] <= 10.0  # roughly the 10s delta, never negative


def test_retry_after_past_http_date_floors_at_zero(
    respx_mock: Any, mock_token: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps = []
    monkeypatch.setattr(
        "smileid.client.transport.time.sleep", lambda s: sleeps.append(s)
    )
    route = respx_mock.get(f"{BASE_URL}/v3/services/id_status").mock(
        side_effect=[
            httpx.Response(
                429,
                headers={"Retry-After": "Mon, 01 Jan 2001 00:00:00 GMT"},
                json={"status": "x", "message": "y"},
            ),
            httpx.Response(200, json={}),
        ]
    )
    client = make_client()
    client.services.id_status(country="NG", id_type="NIN")
    assert route.call_count == 2
    assert sleeps == [0.0]


def test_retry_after_capped_at_60_seconds(
    respx_mock: Any, mock_token: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps = []
    monkeypatch.setattr(
        "smileid.client.transport.time.sleep", lambda s: sleeps.append(s)
    )
    route = respx_mock.get(f"{BASE_URL}/v3/services/id_status").mock(
        side_effect=[
            httpx.Response(
                429, headers={"Retry-After": "3600"}, json={"status": "x", "message": "y"}
            ),
            httpx.Response(200, json={}),
        ]
    )
    client = make_client()
    client.services.id_status(country="NG", id_type="NIN")
    assert route.call_count == 2
    assert sleeps == [60.0]  # capped, never an unbounded sleep


def test_retry_after_unparseable_falls_back_to_backoff(
    respx_mock: Any, mock_token: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps = []
    monkeypatch.setattr(
        "smileid.client.transport.time.sleep", lambda s: sleeps.append(s)
    )
    route = respx_mock.get(f"{BASE_URL}/v3/services/id_status").mock(
        side_effect=[
            httpx.Response(
                429, headers={"Retry-After": "soonish"}, json={"status": "x", "message": "y"}
            ),
            httpx.Response(200, json={}),
        ]
    )
    client = make_client()
    client.services.id_status(country="NG", id_type="NIN")
    assert route.call_count == 2
    assert len(sleeps) == 1
    assert sleeps[0] > 0  # exponential backoff used instead


def test_entry_post_never_retried_on_500(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(500, json={"status": "Server Error", "message": "boom"})
    )
    client = make_client()
    with pytest.raises(smileid.errors.APIError):
        client.enhanced_kyc.verify(
            country="NG",
            id_type="NIN",
            id_number="12345678901",
            user_details=user_details_dict(),
            consent=consent_dict(),
        )
    assert route.call_count == 1  # mutating POSTs are never auto-retried


def test_entry_post_connection_error_surfaces(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        side_effect=httpx.ConnectError("dns")
    )
    client = make_client()
    with pytest.raises(smileid.errors.ConnectionError):
        client.enhanced_kyc.verify(
            country="NG",
            id_type="NIN",
            id_number="12345678901",
            user_details=user_details_dict(),
            consent=consent_dict(),
        )
    assert route.call_count == 1


def test_get_retries_connection_error(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.get(f"{BASE_URL}/v3/services/id_status").mock(
        side_effect=[httpx.ConnectError("dns"), httpx.Response(200, json={})]
    )
    client = make_client()
    client.services.id_status(country="NG", id_type="NIN")
    assert route.call_count == 2


def test_replay_409_never_retried_raises_conflict(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/replay/job_x").mock(
        return_value=httpx.Response(
            409,
            json={"status": "Conflict", "message": "Verification is still processing."},
        )
    )
    client = make_client()
    with pytest.raises(smileid.errors.ConflictError):
        client.verifications.replay("job_x")
    assert route.call_count == 1  # 409 is never auto-retried


def test_max_retries_exhausted(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.get(f"{BASE_URL}/v3/services/id_status").mock(
        return_value=httpx.Response(503, json={"status": "x", "message": "y"})
    )
    client = make_client(max_retries=2)
    with pytest.raises(smileid.errors.APIError):
        client.services.id_status(country="NG", id_type="NIN")
    assert route.call_count == 3  # initial + 2 retries
