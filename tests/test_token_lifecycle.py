"""Matrix item 2: JWT token lifecycle (spec §2.3, §2A)."""

from __future__ import annotations

import threading
from typing import Any

import httpx
import pytest

import smileid
from tests.conftest import BASE_URL, consent_dict, make_client, make_jwt, user_details_dict

ACCEPTED = {"status": "Accepted", "job_id": "job_x", "user_id": "user_x"}


def _enhanced_kyc(client: smileid.Client) -> Any:
    return client.enhanced_kyc.verify(
        country="NG",
        id_type="NIN",
        id_number="12345678901",
        user_details=user_details_dict(),
        consent=consent_dict(),
    )


def test_token_cached_across_calls(respx_mock: Any) -> None:
    token_route = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": make_jwt(exp_offset=3600)})
    )
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    client = make_client()
    _enhanced_kyc(client)
    _enhanced_kyc(client)
    _enhanced_kyc(client)
    assert token_route.call_count == 1  # cached until exp - 60s


def test_token_refetched_when_expired(respx_mock: Any) -> None:
    # exp is within the 60s skew window, so the token is always treated stale.
    token_route = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": make_jwt(exp_offset=30)})
    )
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    client = make_client()
    _enhanced_kyc(client)
    _enhanced_kyc(client)
    assert token_route.call_count == 2


def test_refresh_on_401_once_then_success(respx_mock: Any) -> None:
    token_route = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": make_jwt()})
    )
    kyc_route = respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        side_effect=[
            httpx.Response(401, json={"status": "Unauthorized", "message": "expired"}),
            httpx.Response(202, json=ACCEPTED),
        ]
    )
    client = make_client()
    result = _enhanced_kyc(client)
    assert result.is_accepted
    assert kyc_route.call_count == 2  # original + one retry
    assert token_route.call_count == 2  # initial fetch + one refresh


def test_second_401_raises_authentication_error(respx_mock: Any) -> None:
    respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": make_jwt()})
    )
    kyc_route = respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(401, json={"status": "Unauthorized", "message": "nope"})
    )
    client = make_client()
    with pytest.raises(smileid.errors.AuthenticationError):
        _enhanced_kyc(client)
    assert kyc_route.call_count == 2  # tried once, refreshed, tried once more


def test_token_cache_is_thread_safe(respx_mock: Any) -> None:
    token_route = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": make_jwt(exp_offset=3600)})
    )
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    client = make_client()

    def worker() -> None:
        _enhanced_kyc(client)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    # Concurrent callers must not stampede the token endpoint.
    assert token_route.call_count == 1


def test_undecodable_jwt_refetched_every_call(respx_mock: Any) -> None:
    token_route = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": "not-a-jwt"})
    )
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    client = make_client()
    _enhanced_kyc(client)
    _enhanced_kyc(client)
    assert token_route.call_count == 2  # null exp => refresh next call
