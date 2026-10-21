"""Matrix item 2: JWT token lifecycle — one token minted per request."""

from __future__ import annotations

import itertools
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
    parse_multipart,
    user_details_dict,
)
from usesmileid.generated import operations

ACCEPTED = {"status": "Accepted", "job_id": "job_x", "user_id": "user_x"}
PROCESSING = {"status": "processing", "job_id": "job_x"}

_KYC_ID = {"country": "NG", "id_type": "NIN", "id_number": "12345678901"}
_DOC_IMAGES = {
    "selfie_image": JPEG_BYTES,
    "liveness_images": LIVENESS,
    "document": JPEG_BYTES,
    "country": "NG",
}
_SELFIE = {"selfie_image": JPEG_BYTES, "liveness_images": LIVENESS}


def _person() -> Dict[str, Any]:
    return {"consent": consent_dict(), "user_details": user_details_dict()}


# operation -> (method, path, status, call with user "user-1")
_OPERATIONS: Dict[str, Any] = {
    "enhanced_kyc": (
        "POST",
        "/v3/enhanced_kyc",
        202,
        lambda c: c.enhanced_kyc.verify(**_KYC_ID, **_person(), user_id="user-1"),
    ),
    "document_verification": (
        "POST",
        "/v3/document_verification",
        202,
        lambda c: c.documents.verify(**_DOC_IMAGES, **_person(), user_id="user-1"),
    ),
    "enhanced_document_verification": (
        "POST",
        "/v3/enhanced_document_verification",
        202,
        lambda c: c.documents.verify_enhanced(
            **_DOC_IMAGES, id_type="PASSPORT", **_person(), user_id="user-1"
        ),
    ),
    "residency_document_verification": (
        "POST",
        "/v3/residency_document_verification",
        202,
        lambda c: c.documents.verify_residency(
            **_DOC_IMAGES, visa=JPEG_BYTES, **_person(), user_id="user-1"
        ),
    ),
    "biometric_kyc": (
        "POST",
        "/v3/biometric_kyc",
        202,
        lambda c: c.biometric_kyc.verify(**_KYC_ID, **_SELFIE, **_person(), user_id="user-1"),
    ),
    "smart_selfie_registration": (
        "POST",
        "/v3/registration",
        202,
        lambda c: c.biometric.enroll(**_SELFIE, **_person(), user_id="user-1"),
    ),
    "smart_selfie_authentication": (
        "POST",
        "/v3/authentication",
        202,
        lambda c: c.biometric.authenticate(**_SELFIE, **_person(), user_id="user-1"),
    ),
    "smart_selfie_compare": (
        "POST",
        "/v3/compare",
        202,
        lambda c: c.biometric.compare(
            selfie_image=JPEG_BYTES,
            comparison_image=JPEG_BYTES,
            comparison_image_type="id_card",
            **_person(),
            user_id="user-1",
        ),
    ),
}

_UNBOUND: Dict[str, Any] = {
    "status": ("GET", "/v3/status/job_x", 200, lambda c: c.verifications.retrieve("job_x")),
    "replay": ("POST", "/v3/replay/job_x", 202, lambda c: c.verifications.replay("job_x")),
    "report_fraud": (
        "POST",
        "/v3/users/user-1/report_fraud",
        200,
        lambda c: c.users.flag_fraud(
            "user-1", reason="ACCOUNT_TAKEOVER", reported_by="risk@partner.example"
        ),
    ),
    "id_status": (
        "GET",
        "/v3/services/id_status",
        200,
        lambda c: c.services.id_status(country="NG", id_type="NIN"),
    ),
}


def _enhanced_kyc(client: usesmileid.Client, **kwargs: Any) -> Any:
    return client.enhanced_kyc.verify(**_KYC_ID, **_person(), **kwargs)


def _enrolled_kyc(client: usesmileid.Client, **kwargs: Any) -> Any:
    return client.biometric_kyc.verify(
        use_enrolled_image=True, user_id="user-1", **_KYC_ID, **_person(), **kwargs
    )


def _token_claims(request: httpx.Request) -> Dict[str, str]:
    if not request.content:
        return {}
    return {p["name"]: p["body"].decode() for p in parse_multipart(request)}


def _token_route(respx_mock: Any) -> Any:
    """Mint ``token-1``, ``token-2``, ... so each request's token is identifiable."""
    counter = itertools.count(1)
    return respx_mock.post(f"{BASE_URL}/v3/token").mock(
        side_effect=lambda _request: httpx.Response(200, json={"token": f"token-{next(counter)}"})
    )


def _route(respx_mock: Any, method: str, path: str, status: int) -> Any:
    body = ACCEPTED if status == 202 else PROCESSING
    return respx_mock.route(method=method, url=f"{BASE_URL}{path}").mock(
        return_value=httpx.Response(status, json=body)
    )


@pytest.mark.parametrize("product", sorted(_OPERATIONS))
def test_job_token_binds_its_user_and_product(respx_mock: Any, product: str) -> None:
    method, path, status, call = _OPERATIONS[product]
    token_route = _token_route(respx_mock)
    _route(respx_mock, method, path, status)
    call(make_client())
    assert _token_claims(token_route.calls.last.request) == {
        "user_id": "user-1",
        "product": product,
    }


@pytest.mark.parametrize("name", sorted(_UNBOUND))
def test_non_job_token_binds_nothing(respx_mock: Any, name: str) -> None:
    method, path, status, call = _UNBOUND[name]
    token_route = _token_route(respx_mock)
    _route(respx_mock, method, path, status)
    call(make_client())
    assert token_route.call_count == 1
    assert token_route.calls.last.request.content == b""


def test_job_without_user_binds_only_product(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    _route(respx_mock, "POST", "/v3/enhanced_kyc", 202)
    _enhanced_kyc(make_client())
    assert _token_claims(token_route.calls.last.request) == {"product": "enhanced_kyc"}


def test_each_job_sends_the_token_minted_for_it(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    kyc_route = _route(respx_mock, "POST", "/v3/enhanced_kyc", 202)
    client = make_client()
    for _ in range(3):
        _enhanced_kyc(client)
    assert token_route.call_count == 3
    sent = [call.request.headers["SmileID-Token"] for call in kyc_route.calls]
    assert sent == ["token-1", "token-2", "token-3"]


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
            httpx.Response(200, json=PROCESSING),
        ]
    )
    make_client().verifications.retrieve("job_x")
    assert token_route.call_count == 1
    sent = [call.request.headers["SmileID-Token"] for call in status_route.calls]
    assert sent == ["token-1", "token-1"]


@pytest.mark.parametrize(
    ("response", "error"),
    [
        (httpx.Response(401, json={"status": "Unauthorized", "message": "bad key"}),
         usesmileid.errors.AuthenticationError),
        (httpx.Response(503, json={"status": "error", "message": "busy"}),
         usesmileid.errors.APIError),
        (httpx.Response(200, json={"token": ""}), usesmileid.errors.UnexpectedResponseError),
    ],
    ids=["401", "503", "empty-token"],
)
def test_failed_mint_never_sends_the_job(
    respx_mock: Any, response: httpx.Response, error: type
) -> None:
    respx_mock.post(f"{BASE_URL}/v3/token").mock(return_value=response)
    kyc_route = _route(respx_mock, "POST", "/v3/enhanced_kyc", 202)
    with pytest.raises(error):
        _enhanced_kyc(make_client())
    assert not kyc_route.called


def test_mint_uses_the_request_timeout(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    _route(respx_mock, "POST", "/v3/enhanced_kyc", 202)
    _enhanced_kyc(make_client(), timeout=7.0)
    assert token_route.calls.last.request.extensions["timeout"]["read"] == 7.0


@pytest.mark.parametrize("user_id", ["", " user-1", "user-1 "])
def test_empty_or_padded_user_id_is_rejected(respx_mock: Any, user_id: str) -> None:
    with pytest.raises(usesmileid.errors.ValidationError, match="user_id"):
        _enhanced_kyc(make_client(), user_id=user_id)
    assert not respx_mock.calls


def test_enrolled_image_grant_is_bound_to_the_job_token(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    kyc_route = _route(respx_mock, "POST", "/v3/biometric_kyc", 202)
    _enrolled_kyc(make_client())
    assert _token_claims(token_route.calls.last.request) == {
        "user_id": "user-1",
        "product": "biometric_kyc",
        "use_enrolled_image": "true",
    }
    job_parts = {p["name"] for p in parse_multipart(kyc_route.calls.last.request)}
    assert not job_parts & {"use_enrolled_image", "selfie_image", "liveness_images"}


def test_grant_does_not_reach_later_requests(respx_mock: Any) -> None:
    token_route = _token_route(respx_mock)
    kyc_route = _route(respx_mock, "POST", "/v3/biometric_kyc", 202)
    status_route = _route(respx_mock, "GET", "/v3/status/job_x", 200)
    client = make_client()
    _enrolled_kyc(client)
    client.verifications.retrieve("job_x")
    assert kyc_route.calls.last.request.headers["SmileID-Token"] == "token-1"
    assert status_route.calls.last.request.headers["SmileID-Token"] == "token-2"
    assert _token_claims(token_route.calls.last.request) == {}


def test_transport_refuses_a_grant_without_a_user(respx_mock: Any) -> None:
    client = make_client()
    request = operations.biometric_kyc(
        consent=consent_dict(),
        user_details=user_details_dict(),
        **_KYC_ID,
    )
    with pytest.raises(usesmileid.errors.ValidationError, match="user_id"):
        client._transport.send(request, use_enrolled_image=True)
    assert not respx_mock.calls


@pytest.mark.parametrize("value", ["true", "false", 1])
def test_grant_accepts_only_a_bool(respx_mock: Any, value: Any) -> None:
    with pytest.raises(usesmileid.errors.ValidationError, match="bool"):
        make_client().biometric_kyc.verify(
            use_enrolled_image=value, user_id="user-1", **_KYC_ID, **_person()
        )
    assert not respx_mock.calls


