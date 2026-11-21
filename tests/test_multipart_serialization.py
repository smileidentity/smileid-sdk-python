"""Matrix item 1: golden multipart wire shape and header routing."""

from __future__ import annotations

import json
from typing import Any

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
    part_names,
    user_details_dict,
)

ACCEPTED = {
    "status": "Accepted",
    "message": "Request accepted and queued for processing.",
    "job_id": "job_01h8x9y2z3a4b5c6d7e8f9g0h1",
    "user_id": "user_01h8x9y2z3a4b5c6d7e8f9g0h1",
}
ACCEPTED_LOWER = {**ACCEPTED, "status": "accepted"}


def test_enhanced_kyc_multipart_shape(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    client = make_client()
    client.enhanced_kyc.verify(
        country="NG",
        id_type="NIN",
        id_number="12345678901",
        user_details=user_details_dict(),
        consent=consent_dict(),
        user_id="user_01h8x9y2z3a4b5c6d7e8f9g0h1",
    )

    request = route.calls.last.request
    parts = parse_multipart(request)
    by_name = {p["name"]: p for p in parts}

    # Scalars are plain text parts with no Content-Type.
    assert by_name["country"]["body"] == b"NG"
    assert by_name["country"]["content_type"] is None
    assert by_name["id_type"]["body"] == b"NIN"
    assert by_name["id_number"]["body"] == b"12345678901"

    # Object fields are JSON parts with application/json and no filename.
    assert by_name["user_details"]["content_type"] == "application/json"
    assert by_name["user_details"]["filename"] is None
    assert json.loads(by_name["user_details"]["body"]) == user_details_dict()
    assert by_name["consent"]["content_type"] == "application/json"
    assert json.loads(by_name["consent"]["body"]) == consent_dict()

    # user_id routes to the User-ID header, not the body; no Partner-ID header.
    assert request.headers["User-ID"] == "user_01h8x9y2z3a4b5c6d7e8f9g0h1"
    assert "SmileID-Partner-ID" not in request.headers
    assert request.headers["SmileID-Token"]  # injected

    # Telemetry headers always present.
    assert request.headers["SmileID-Source-SDK"] == "python"
    assert request.headers["SmileID-Source-SDK-Version"] == usesmileid.__version__
    assert request.headers["User-Agent"].startswith(f"smileid-sdk-python/{usesmileid.__version__}")


def test_document_verification_repeated_liveness_and_partner_id(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/document_verification").mock(
        return_value=httpx.Response(202, json=ACCEPTED_LOWER)
    )
    client = make_client()
    client.documents.verify(
        selfie_image=JPEG_BYTES,
        liveness_images=LIVENESS,
        document=JPEG_BYTES,
        consent=consent_dict(),
        country="NG",
        user_details=user_details_dict(),
    )

    request = route.calls.last.request
    parts = parse_multipart(request)
    names = part_names(parts)

    # liveness_images is a REPEATED part, never CSV/indexed.
    assert names.count("liveness_images") == 6
    for part in parts:
        if part["name"] == "liveness_images":
            assert part["content_type"] == "image/jpeg"
            assert part["filename"]  # each has a filename

    # Binary parts carry filename + content type.
    selfie = next(p for p in parts if p["name"] == "selfie_image")
    assert selfie["filename"] == "selfie.jpg"
    assert selfie["content_type"] == "image/jpeg"
    document = next(p for p in parts if p["name"] == "document")
    assert document["content_type"] == "image/jpeg"

    # Partner-ID header required on this endpoint.
    assert request.headers["SmileID-Partner-ID"] == "1234"


def test_residency_document_verification_sends_visa(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/residency_document_verification").mock(
        return_value=httpx.Response(202, json=ACCEPTED_LOWER)
    )
    png = b"\x89PNG\r\n\x1a\n" + b"body"
    client = make_client()
    client.documents.verify_residency(
        selfie_image=JPEG_BYTES,
        liveness_images=LIVENESS,
        document=JPEG_BYTES,
        visa=png,
        consent=consent_dict(),
        country="ZA",
        user_details=user_details_dict(),
    )

    request = route.calls.last.request
    parts = parse_multipart(request)
    by_name = {p["name"]: p for p in parts}
    assert by_name["id_type"]["body"] == b"PASSPORT"
    assert by_name["visa"]["content_type"] == "image/png"
    assert by_name["visa"]["filename"] == "visa.jpg"
    assert part_names(parts).count("liveness_images") == 6
    assert request.headers["SmileID-Partner-ID"] == "1234"


def test_document_back_png_detected(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/document_verification").mock(
        return_value=httpx.Response(202, json=ACCEPTED_LOWER)
    )
    png = b"\x89PNG\r\n\x1a\n" + b"body"
    client = make_client()
    client.documents.verify(
        selfie_image=JPEG_BYTES,
        liveness_images=LIVENESS,
        document=png,
        document_back=png,
        consent=consent_dict(),
        country="NG",
        user_details=user_details_dict(),
    )
    parts = parse_multipart(route.calls.last.request)
    document = next(p for p in parts if p["name"] == "document")
    assert document["content_type"] == "image/png"
    document_back = next(p for p in parts if p["name"] == "document_back")
    assert document_back["content_type"] == "image/png"


def test_selfie_and_liveness_always_jpeg_even_for_png_bytes(
    respx_mock: Any, mock_token: Any
) -> None:
    """PNG is only valid for document / document_back; selfie-family inputs
    must always be sent as image/jpeg."""
    route = respx_mock.post(f"{BASE_URL}/v3/document_verification").mock(
        return_value=httpx.Response(202, json=ACCEPTED_LOWER)
    )
    png = b"\x89PNG\r\n\x1a\n" + b"body"
    client = make_client()
    client.documents.verify(
        selfie_image=png,
        liveness_images=[png] * 6,
        document=JPEG_BYTES,
        consent=consent_dict(),
        country="NG",
        user_details=user_details_dict(),
    )
    parts = parse_multipart(route.calls.last.request)
    selfie = next(p for p in parts if p["name"] == "selfie_image")
    assert selfie["content_type"] == "image/jpeg"
    for part in parts:
        if part["name"] == "liveness_images":
            assert part["content_type"] == "image/jpeg"


def test_comparison_image_always_jpeg(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/compare").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    png = b"\x89PNG\r\n\x1a\n" + b"body"
    client = make_client()
    client.biometric.compare(
        selfie_image=JPEG_BYTES,
        comparison_image=png,
        comparison_image_type="ID_PHOTO",
        consent=consent_dict(),
        user_details=user_details_dict(),
    )
    parts = parse_multipart(route.calls.last.request)
    comparison = next(p for p in parts if p["name"] == "comparison_image")
    assert comparison["content_type"] == "image/jpeg"


def test_authentication_user_id_in_body_not_header(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/authentication").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    client = make_client()
    client.biometric.authenticate(
        user_id="user_01h8x9y2z3a4b5c6d7e8f9g0h1",
        selfie_image=JPEG_BYTES,
        liveness_images=LIVENESS,
        consent=consent_dict(),
        user_details=user_details_dict(),
    )
    request = route.calls.last.request
    parts = parse_multipart(request)
    by_name = {p["name"]: p for p in parts}
    assert by_name["user_id"]["body"] == b"user_01h8x9y2z3a4b5c6d7e8f9g0h1"
    assert "User-ID" not in request.headers
    assert "SmileID-Partner-ID" not in request.headers


def test_report_fraud_is_multipart_with_scalars(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(
        f"{BASE_URL}/v3/users/user-123/report_fraud"
    ).mock(
        return_value=httpx.Response(
            202,
            json={
                "status": "accepted",
                "message": "Fraud report accepted",
                "user_id": "user-123",
            },
        )
    )
    client = make_client()
    client.users.flag_fraud(
        "user-123", reason="FIRST_PARTY_FRAUD", reported_by="risk@partner.example"
    )
    request = route.calls.last.request
    parts = parse_multipart(request)  # asserts multipart even with only scalars
    by_name = {p["name"]: p for p in parts}
    assert by_name["is_fraud"]["body"] == b"true"
    assert by_name["reason"]["body"] == b"FIRST_PARTY_FRAUD"
    assert by_name["reported_by"]["body"] == b"risk@partner.example"


def test_replay_with_override_sends_multipart_callback_url(
    respx_mock: Any, mock_token: Any
) -> None:
    """Replay takes multipart/form-data, not JSON (415 otherwise)."""
    route = respx_mock.post(
        f"{BASE_URL}/v3/replay/job_01h8x9y2z3a4b5c6d7e8f9g0h1"
    ).mock(
        return_value=httpx.Response(
            202,
            json={
                "status": "accepted",
                "job_id": "job_01h8x9y2z3a4b5c6d7e8f9g0h1",
                "user_id": "test-user",
                "message": "Callback replay queued successfully.",
            },
        )
    )
    client = make_client()
    client.verifications.replay(
        "job_01h8x9y2z3a4b5c6d7e8f9g0h1",
        callback_url="https://partner.example.com/webhook",
    )
    request = route.calls.last.request
    assert request.headers["content-type"].startswith("multipart/form-data")
    parts = parse_multipart(request)
    assert [p["name"] for p in parts] == ["callback_url"]
    part = parts[0]
    assert part["body"] == b"https://partner.example.com/webhook"
    assert part["content_type"] is None  # plain text part
    assert part["filename"] is None


def test_replay_without_override_sends_no_body(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(
        f"{BASE_URL}/v3/replay/job_01h8x9y2z3a4b5c6d7e8f9g0h1"
    ).mock(return_value=httpx.Response(202, json={"status": "accepted"}))
    client = make_client()
    client.verifications.replay("job_01h8x9y2z3a4b5c6d7e8f9g0h1")
    request = route.calls.last.request
    assert request.content == b""
    assert "content-type" not in request.headers


def test_token_endpoint_lowercase_headers_and_no_body(respx_mock: Any) -> None:
    from tests.conftest import make_jwt

    token_route = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": make_jwt()})
    )
    respx_mock.get(f"{BASE_URL}/v3/services/id_status").mock(
        return_value=httpx.Response(200, json={})
    )
    client = make_client()
    client.services.id_status(country="NG", id_type="NIN")

    token_request = token_route.calls.last.request
    assert token_request.headers["smileid-partner-id"] == "1234"
    assert token_request.headers["smileid-api-key"] == "test-api-key"
    assert token_request.content == b""  # SDK sends no body
    # Telemetry still sent on the token call.
    assert token_request.headers["SmileID-Source-SDK"] == "python"


def test_unauthenticated_services_send_no_token(respx_mock: Any) -> None:
    token_route = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": "unused"})
    )
    route = respx_mock.get(f"{BASE_URL}/v3/services/bank_codes").mock(
        return_value=httpx.Response(200, json={"bank_codes": []})
    )
    client = make_client()
    client.services.bank_codes()

    assert not token_route.called  # no token fetched for unauthenticated ops
    assert "SmileID-Token" not in route.calls.last.request.headers


AML_KWARGS: dict = {
    "countries": ["NG", "KE"],
    "full_name": "John Doe",
    "user_details": user_details_dict(),
    "consent": consent_dict(),
}

AML_RESULT = {
    "status": "block",
    "message": "Screening completed: potential matches identified.",
    "reason": "aml_match_found",
    "created_at": "2026-07-20T12:00:00.000Z",
    "completed_at": "2026-07-20T12:00:01.000Z",
    "product": "one_time_aml",
    "partner_params": None,
    "kyc_receipt": "https://receipts.smileidentity.com/abc",
    "strict_match": True,
    "no_of_persons_found": 1,
    "people": [{"name": "Gbenga Afolabi", "sanctions": [{"list": "OFAC SDN"}]}],
    "user_provided_info": {
        "given_names": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone_number": None,
    },
    "consent": {},
    "antifraud": None,
    "device_signals": None,
}


def test_one_time_aml_multipart_shape(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/aml").mock(
        return_value=httpx.Response(202, json=ACCEPTED_LOWER)
    )
    accepted = make_client().aml.screen(
        **AML_KWARGS,
        birth_year="1990",
        strict_match=False,
        aliases=["Johnny Doe"],
        search_existing_user=True,
        user_id="user-1234",
        callback_url="https://example.com/callback",
        partner_params={"order_id": "ORD-1"},
        metadata=[{"name": "k", "value": "v"}],
    )
    assert accepted.is_accepted
    assert accepted.job_id == ACCEPTED["job_id"]

    request = route.calls.last.request
    parts = parse_multipart(request)
    by_name = {p["name"]: p for p in parts}
    assert part_names(parts) == [
        "full_name",
        "birth_year",
        "strict_match",
        "search_existing_user",
        "user_id",
        "callback_url",
        "countries",
        "aliases",
        "user_details",
        "consent",
        "partner_params",
        "metadata",
    ]
    assert by_name["full_name"]["body"] == b"John Doe"
    assert by_name["birth_year"]["body"] == b"1990"
    assert by_name["strict_match"]["body"] == b"false"
    assert by_name["search_existing_user"]["body"] == b"true"
    assert by_name["user_id"]["body"] == b"user-1234"
    assert by_name["callback_url"]["body"] == b"https://example.com/callback"
    # Arrays are single JSON-encoded parts, never repeated fields.
    assert by_name["countries"]["content_type"] == "application/json"
    assert by_name["countries"]["body"] == b'["NG","KE"]'
    assert by_name["aliases"]["body"] == b'["Johnny Doe"]'
    assert json.loads(by_name["consent"]["body"]) == consent_dict()
    assert json.loads(by_name["partner_params"]["body"]) == {"order_id": "ORD-1"}
    assert request.headers["SmileID-Token"]
    assert "User-ID" not in request.headers
    assert "SmileID-Idempotency-Key" not in request.headers


def test_one_time_aml_sync_returns_result_and_sends_idempotency_key(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/aml/sync").mock(
        return_value=httpx.Response(200, json=AML_RESULT, headers={"SmileID-Job-ID": "job_aml"})
    )
    result = make_client().aml.screen_sync(**AML_KWARGS, idempotency_key="kuda-onboarding-8f14e45f")

    assert result.status == "block"
    assert result.job_id == "job_aml"
    assert result.reason == "aml_match_found"
    assert result.no_of_persons_found == 1
    assert result.people[0]["name"] == "Gbenga Afolabi"
    assert result.user_provided_info is not None
    assert result.user_provided_info.given_names == "John"
    assert result.kyc_receipt == "https://receipts.smileidentity.com/abc"

    request = route.calls.last.request
    assert request.headers["SmileID-Idempotency-Key"] == "kuda-onboarding-8f14e45f"
    by_name = {p["name"]: p for p in parse_multipart(request)}
    assert by_name["countries"]["body"] == b'["NG","KE"]'
    assert "callback_url" not in by_name


def test_one_time_aml_sync_retries_only_with_idempotency_key(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/aml/sync").mock(
        side_effect=[
            httpx.Response(503, json={"message": "later"}),
            httpx.Response(200, json=AML_RESULT),
        ]
    )
    result = make_client().aml.screen_sync(**AML_KWARGS, idempotency_key="kuda-onboarding-8f14e45f")
    assert result.status == "block"
    assert route.call_count == 2

    route.reset()
    route.mock(return_value=httpx.Response(503, json={"message": "later"}))
    with pytest.raises(usesmileid.errors.SmileIDError):
        make_client().aml.screen_sync(**AML_KWARGS)
    assert route.call_count == 1


@pytest.mark.parametrize("status_code", [408, 500])
def test_one_time_aml_sync_without_key_is_not_retried_and_carries_job_id(
    respx_mock: Any, mock_token: Any, status_code: int
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/aml/sync").mock(
        return_value=httpx.Response(
            status_code, json={"message": "x"}, headers={"SmileID-Job-ID": "job_aml"}
        )
    )
    with pytest.raises(usesmileid.errors.SmileIDError) as raised:
        make_client().aml.screen_sync(**AML_KWARGS)
    assert raised.value.status_code == status_code
    assert raised.value.job_id == "job_aml"
    assert route.call_count == 1


def test_aml_monitoring_multipart_shape(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/aml/monitoring").mock(
        return_value=httpx.Response(
            202, json={**ACCEPTED_LOWER, "created_at": "2026-03-10T12:00:00.000Z"}
        )
    )
    accepted = make_client().aml.monitor(
        countries=["NG", "GH"],
        user_details=user_details_dict(),
        consent=consent_dict(),
        search_existing_user=True,
        user_id="user-1234",
    )
    assert accepted.is_accepted
    assert accepted.created_at == "2026-03-10T12:00:00.000Z"

    parts = parse_multipart(route.calls.last.request)
    assert part_names(parts) == [
        "search_existing_user",
        "user_id",
        "countries",
        "user_details",
        "consent",
    ]
    by_name = {p["name"]: p for p in parts}
    assert by_name["countries"]["body"] == b'["NG","GH"]'
    assert by_name["search_existing_user"]["body"] == b"true"


NEWS = {
    "job_id": "a1b2c3d4e5",
    "product": "aml_monitoring_news",
    "user_id": "user_123",
    "meta": {"current_page": 2, "limit": 10, "total_count": 11},
    "news": [
        {
            "body": "Sample adverse-media content.",
            "published_date": "2026-01-15T12:00:00.000Z",
            "publisher": "Example News Publisher",
            "publisher_country_code": "NG",
            "title": "Sample AML Monitoring News Item",
            "url": "https://example.com/news/sample",
        }
    ],
}


def test_aml_monitoring_news_request_and_response(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.get(f"{BASE_URL}/v3/aml/monitoring/a1b2c3d4e5/news/ref%2F001").mock(
        return_value=httpx.Response(200, json=NEWS)
    )
    news = make_client().aml.monitoring_news(
        "a1b2c3d4e5", "ref/001", news_category="financial_crime", page=2, limit=10
    )
    request = route.calls.last.request
    assert dict(request.url.params) == {
        "news_category": "financial_crime",
        "page": "2",
        "limit": "10",
    }
    assert request.headers["SmileID-Token"]
    assert request.content == b""
    assert news.meta.current_page == 2
    assert news.meta.total_count == 11
    assert news.news[0].publisher_country_code == "NG"
    assert news.news[0].title == "Sample AML Monitoring News Item"


def test_aml_monitoring_news_omits_unset_paging(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.get(f"{BASE_URL}/v3/aml/monitoring/job1/news/ref1").mock(
        return_value=httpx.Response(200, json={**NEWS, "news": []})
    )
    news = make_client().aml.monitoring_news("job1", "ref1", news_category="other")
    assert dict(route.calls.last.request.url.params) == {"news_category": "other"}
    assert news.news == []


BASIC_KYC_KWARGS: dict = {
    "country": "NG",
    "id_type": "NIN",
    "id_number": "12345678901",
    "user_details": user_details_dict(),
    "consent": consent_dict(),
}

BASIC_KYC_RESULT = {
    "status": "attention",
    "message": "Verification completed: partial match.",
    "reason": None,
    "created_at": "2026-03-10T12:00:00.000Z",
    "completed_at": "2026-03-10T12:00:04.000Z",
    "product": "basic_kyc",
    "partner_params": {"order_id": "ORD-12345"},
    "match_results": {
        "overall": "partial_match",
        "names": "partial_match",
        "first_name": "exact_match",
        "last_name": "transposed",
        "other_names": "not_provided",
        "date_of_birth": "no_match",
        "gender": "exact_match",
        "phone_number": "not_provided",
        "secondary_id_number": "not_provided",
    },
    "user_provided_info": {
        "given_names": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "phone_number": None,
        "id_number": "12345678901",
    },
    "consent": {},
    "antifraud": None,
    "device_signals": None,
    "kyc_receipt": "https://portal.example/receipt",
}


def test_basic_kyc_multipart_shape(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/basic_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED_LOWER)
    )
    accepted = make_client().basic_kyc.verify(
        **BASIC_KYC_KWARGS,
        callback_url="https://example.com/callback",
        bank_code="044",
        operator="mtn",
        partner_params={"order_id": "ORD-1"},
        metadata=[{"name": "k", "value": "v"}],
    )
    assert accepted.is_accepted

    request = route.calls.last.request
    parts = parse_multipart(request)
    by_name = {p["name"]: p for p in parts}
    assert len(parts) == len(by_name), "a multipart part name appears twice"
    assert list(by_name) == [
        "country",
        "id_type",
        "id_number",
        "callback_url",
        "bank_code",
        "operator",
        "user_details",
        "consent",
        "partner_params",
        "metadata",
    ]
    assert by_name["country"]["body"] == b"NG"
    assert by_name["country"]["content_type"] is None
    assert by_name["id_number"]["body"] == b"12345678901"
    assert by_name["callback_url"]["body"] == b"https://example.com/callback"
    assert by_name["bank_code"]["body"] == b"044"
    assert by_name["operator"]["body"] == b"mtn"
    assert by_name["user_details"]["content_type"] == "application/json"
    assert json.loads(by_name["user_details"]["body"]) == user_details_dict()
    assert json.loads(by_name["consent"]["body"]) == consent_dict()
    assert json.loads(by_name["partner_params"]["body"]) == {"order_id": "ORD-1"}
    assert json.loads(by_name["metadata"]["body"]) == [{"name": "k", "value": "v"}]
    assert "User-ID" not in request.headers
    assert "SmileID-Partner-ID" not in request.headers
    assert request.headers["SmileID-Token"]
    assert request.headers["SmileID-Source-SDK"] == "python"


def test_basic_kyc_sync_returns_result_and_is_never_retried(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/basic_kyc/sync").mock(
        return_value=httpx.Response(
            200, json=BASIC_KYC_RESULT, headers={"SmileID-Job-ID": "job_basic"}
        )
    )
    result = make_client().basic_kyc.verify_sync(**BASIC_KYC_KWARGS)

    assert result.status == "attention"
    assert result.job_id == "job_basic"
    assert result.reason is None
    assert result.product == "basic_kyc"
    assert result.match_results is not None
    assert result.match_results.overall == "partial_match"
    assert result.match_results.last_name == "transposed"
    assert result.match_results.secondary_id_number == "not_provided"
    assert result.user_provided_info is not None
    assert result.user_provided_info.id_number == "12345678901"
    assert result.partner_params == {"order_id": "ORD-12345"}
    assert result.kyc_receipt == "https://portal.example/receipt"

    request = route.calls.last.request
    parts = parse_multipart(request)
    by_name = {p["name"]: p for p in parts}
    assert len(parts) == len(by_name), "a multipart part name appears twice"
    assert by_name["id_type"]["body"] == b"NIN"
    assert "callback_url" not in by_name
    assert "User-ID" not in request.headers
    assert "SmileID-Idempotency-Key" not in request.headers


@pytest.mark.parametrize("status_code", [408, 424, 500])
def test_basic_kyc_sync_is_never_retried(
    respx_mock: Any, mock_token: Any, status_code: int
) -> None:
    # 408 and 500 are retried for idempotent requests, so one attempt proves the sync call isn't.
    route = respx_mock.post(f"{BASE_URL}/v3/basic_kyc/sync").mock(
        return_value=httpx.Response(status_code, json={"status": "Error", "message": "x"})
    )
    with pytest.raises(usesmileid.errors.SmileIDError) as raised:
        make_client().basic_kyc.verify_sync(**BASIC_KYC_KWARGS)
    assert raised.value.status_code == status_code
    assert raised.value.job_id is None
    assert route.call_count == 1


def test_basic_kyc_sync_408_reads_the_outcome_from_the_status_endpoint(
    respx_mock: Any, mock_token: Any
) -> None:
    """Follows the README: after a 408, read the job's status rather than resubmit."""
    job_id = "job_01h8x9y2z3a4b5c6d7e8f9g0h1"
    sync_route = respx_mock.post(f"{BASE_URL}/v3/basic_kyc/sync").mock(
        return_value=httpx.Response(
            408,
            json={"status": "Request Timeout", "message": "The ID authority timed out."},
            headers={"SmileID-Job-ID": job_id},
        )
    )
    status_route = respx_mock.get(f"{BASE_URL}/v3/status/{job_id}").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "error",
                "job_id": job_id,
                "user_id": "user_01h8x9y2z3a4b5c6d7e8f9g0h1",
                "message": "Job completed",
            },
        )
    )
    client = make_client()
    with pytest.raises(usesmileid.errors.SmileIDError) as raised:
        client.basic_kyc.verify_sync(**BASIC_KYC_KWARGS)
    err = raised.value
    assert err.status_code == 408
    assert err.job_id == job_id

    status = client.verifications.retrieve(err.job_id)

    assert sync_route.call_count == 1
    assert status_route.call_count == 1
    assert status_route.calls.last.request.url.path == f"/v3/status/{job_id}"
    assert status.status == "error"
    assert status.job_id == job_id
    assert status.is_complete


def test_sync_result_job_id_prefers_the_header_over_the_body(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/basic_kyc/sync").mock(
        return_value=httpx.Response(200, json={**BASIC_KYC_RESULT, "job_id": "job_from_body"})
    )
    assert make_client().basic_kyc.verify_sync(**BASIC_KYC_KWARGS).job_id == "job_from_body"

    route.mock(
        return_value=httpx.Response(
            200,
            json={**BASIC_KYC_RESULT, "job_id": "job_from_body"},
            headers={"smileid-job-id": "job_from_header"},
        )
    )
    assert make_client().basic_kyc.verify_sync(**BASIC_KYC_KWARGS).job_id == "job_from_header"


def test_basic_kyc_sync_parses_a_null_match_results(respx_mock: Any, mock_token: Any) -> None:
    body = {**BASIC_KYC_RESULT, "status": "error", "match_results": None, "kyc_receipt": None}
    respx_mock.post(f"{BASE_URL}/v3/basic_kyc/sync").mock(
        return_value=httpx.Response(200, json=body)
    )
    result = make_client().basic_kyc.verify_sync(**BASIC_KYC_KWARGS)
    assert result.status == "error"
    assert result.match_results is None
    assert result.kyc_receipt is None
    assert result.job_id is None


def test_basic_kyc_sync_never_sends_the_default_callback(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/basic_kyc/sync").mock(
        return_value=httpx.Response(200, json=BASIC_KYC_RESULT)
    )
    client = make_client(default_callback_url="https://example.com/default")
    client.basic_kyc.verify_sync(**BASIC_KYC_KWARGS)
    names = [p["name"] for p in parse_multipart(route.calls.last.request)]
    assert "callback_url" not in names

    client.basic_kyc.verify_sync(**BASIC_KYC_KWARGS, callback_url="https://example.com/given")
    parts = {p["name"]: p for p in parse_multipart(route.calls.last.request)}
    assert parts["callback_url"]["body"] == b"https://example.com/given"


@pytest.mark.parametrize("sync", [False, True])
@pytest.mark.parametrize(
    "change",
    [
        {"user_details": {"given_names": "John", "last_name": "Doe"}},
        {"user_details": {"last_name": "Doe", "email": "john@example.com"}},
        {"callback_url": "http://example.com/callback"},
    ],
    ids=["no-email-or-phone", "no-given-name", "http-callback"],
)
def test_basic_kyc_rejects_invalid_input_before_sending(
    respx_mock: Any, mock_token: Any, sync: bool, change: dict
) -> None:
    path = "/v3/basic_kyc/sync" if sync else "/v3/basic_kyc"
    route = respx_mock.post(f"{BASE_URL}{path}")
    resource = make_client().basic_kyc
    call = resource.verify_sync if sync else resource.verify
    with pytest.raises(usesmileid.errors.ValidationError):
        call(**{**BASIC_KYC_KWARGS, **change})
    assert route.call_count == 0
