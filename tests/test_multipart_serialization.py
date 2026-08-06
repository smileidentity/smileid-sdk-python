"""Matrix item 1: golden multipart wire shape and header routing."""

from __future__ import annotations

import json
from typing import Any

import httpx

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
    assert request.headers["SmileID-Source-SDK-Version"] == "12.0.0"
    assert request.headers["User-Agent"].startswith("smileid-sdk-python/12.0.0")


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
