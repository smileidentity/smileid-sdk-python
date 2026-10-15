"""Matrix item 2: JWT token lifecycle — one token minted per request."""

from __future__ import annotations

from typing import Any, Dict

import httpx
import pytest

import usesmileid
from tests.conftest import (
    BASE_URL,
    JPEG_BYTES,
    LIVENESS,
    consent_dict,
    make_client,
    make_jwt,
    parse_multipart,
    user_details_dict,
)

ACCEPTED = {"status": "Accepted", "job_id": "job_x", "user_id": "user_x"}


def _enhanced_kyc(client: usesmileid.Client, **kwargs: Any) -> Any:
    return client.enhanced_kyc.verify(
        country="NG",
        id_type="NIN",
        id_number="12345678901",
        user_details=user_details_dict(),
        consent=consent_dict(),
        **kwargs,
    )


def _token_claims(request: httpx.Request) -> Dict[str, str]:
    if not request.content:
        return {}
    return {p["name"]: p["body"].decode() for p in parse_multipart(request)}


def _token_route(respx_mock: Any) -> Any:
    return respx_mock.post(f"{BASE_URL}/v3/token").mock(
        side_effect=lambda _request: httpx.Response(200, json={"token": make_jwt()})
    )


def test_each_job_mints_its_own_token(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    client = make_client()
    _enhanced_kyc(client)
    _enhanced_kyc(client)
    _enhanced_kyc(client)
    assert token_route.call_count == 3


def test_token_binds_user_and_product(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    _enhanced_kyc(make_client(), user_id="user-1")
    assert _token_claims(token_route.calls.last.request) == {
        "user_id": "user-1",
        "product": "enhanced_kyc",
    }


def test_token_binds_body_user_id(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    respx_mock.post(f"{BASE_URL}/v3/authentication").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    make_client().biometric.authenticate(
        user_id="user-1",
        selfie_image=JPEG_BYTES,
        liveness_images=LIVENESS,
        consent=consent_dict(),
        user_details=user_details_dict(),
    )
    assert _token_claims(token_route.calls.last.request) == {
        "user_id": "user-1",
        "product": "smart_selfie_authentication",
    }


def test_401_is_not_retried(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    kyc_route = respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(401, json={"status": "Unauthorized", "message": "nope"})
    )
    with pytest.raises(usesmileid.errors.AuthenticationError):
        _enhanced_kyc(make_client())
    assert kyc_route.call_count == 1
    assert token_route.call_count == 1


def test_retries_reuse_the_request_token(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    status_route = respx_mock.get(f"{BASE_URL}/v3/status/job_x").mock(
        side_effect=[
            httpx.Response(503, json={"status": "error", "message": "busy"}),
            httpx.Response(200, json={"status": "processing", "job_id": "job_x"}),
        ]
    )
    make_client().verifications.retrieve("job_x")
    assert status_route.call_count == 2
    assert token_route.call_count == 1
    first, second = (call.request.headers["SmileID-Token"] for call in status_route.calls)
    assert first == second


def test_enrolled_image_grant_is_bound_to_the_job_token(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    kyc_route = respx_mock.post(f"{BASE_URL}/v3/biometric_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    make_client().biometric_kyc.verify(
        use_enrolled_image=True,
        user_id="user-1",
        country="NG",
        id_type="NIN",
        id_number="12345678901",
        consent=consent_dict(),
        user_details=user_details_dict(),
    )
    assert _token_claims(token_route.calls.last.request) == {
        "user_id": "user-1",
        "product": "biometric_kyc",
        "use_enrolled_image": "true",
    }
    job_parts = {p["name"] for p in parse_multipart(kyc_route.calls.last.request)}
    assert not job_parts & {"use_enrolled_image", "selfie_image", "liveness_images"}


def test_grant_does_not_reach_later_requests(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    respx_mock.post(f"{BASE_URL}/v3/biometric_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    respx_mock.get(f"{BASE_URL}/v3/status/job_x").mock(
        return_value=httpx.Response(200, json={"status": "processing", "job_id": "job_x"})
    )
    client = make_client()
    client.biometric_kyc.verify(
        use_enrolled_image=True,
        user_id="user-1",
        country="NG",
        id_type="NIN",
        id_number="12345678901",
        consent=consent_dict(),
        user_details=user_details_dict(),
    )
    client.verifications.retrieve("job_x")
    assert token_route.call_count == 2
    assert _token_claims(token_route.calls.last.request) == {}
