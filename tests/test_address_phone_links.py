"""Address verification, phone verification, Smile Links, and the sync response headers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import httpx
import pytest

import usesmileid
from tests.conftest import (
    BASE_URL,
    consent_dict,
    make_client,
    parse_multipart,
    part_names,
    user_details_dict,
)
from usesmileid.errors import SmileIDError, ValidationError

ACCEPTED = {
    "status": "accepted",
    "message": "Job submitted successfully",
    "job_id": "job_01h8x9y2z3a4b5c6d7e8f9g0h1",
    "user_id": "user_01h8x9y2z3a4b5c6d7e8f9g0h1",
}
REF_ID = "65983864-e8c6-4d09-890a-2e5f88fc50f6"
ID_TYPES = [{"country": "NG", "id_type": "NIN", "verification_method": "enhanced_kyc"}]
LINK = {
    "ref_id": REF_ID,
    "link": f"https://links.usesmileid.com/v3/2/{REF_ID}",
    "name": "Onboarding",
    "company_name": "Acme Pay",
    "description": None,
    "id_types": ID_TYPES,
    "is_single_use": False,
    "callback_url": "https://partner.example/callback",
    "notice_privacy_policy_url": "https://partner.example/privacy",
    "logo_url": "https://portal.usesmileid.com/logo.png",
    "redirect_url": None,
    "theme_color": "#000",
    "expires_at": None,
    "disabled_at": None,
    "partner_params": None,
    "user_id": None,
    "token_provided_fields": ["country", "id_type"],
    "token_provided_values": {"country": "NG", "id_type": "NIN"},
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-20T08:15:00Z",
    "extra_field": 1,
}
STATS = {
    "clear": 12,
    "block": 1,
    "attention": 2,
    "error": 0,
    "successful_jobs": 14,
    "failed_jobs": 1,
    "total_jobs": 15,
}


def _claims(request: httpx.Request) -> Any:
    if not request.content:
        return {}
    return {p["name"]: p["body"].decode() for p in parse_multipart(request)}


# -- address -------------------------------------------------------------


def test_address_verification_golden_request(respx_mock: Any) -> None:
    token = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    route = respx_mock.post(f"{BASE_URL}/v3/address").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    accepted = make_client().address.verify(
        address="12 Test Road, Testville",
        country="NG",
        utility_number="0123456789",
        utility_provider="IKEDC",
        utility_type="PrePaid",
        id_number="9001015800085",
        user_details=user_details_dict(),
        consent=consent_dict(),
        user_id="user-1",
        callback_url="https://example.com/callback",
        partner_params={"order_id": "1"},
        metadata=[{"name": "k", "value": "v"}],
    )
    assert accepted.is_accepted
    assert accepted.job_id == ACCEPTED["job_id"]

    # The token carries the product and the body's user_id.
    assert _claims(token.calls.last.request) == {
        "user_id": "user-1",
        "product": "address_verification",
    }
    request = route.calls.last.request
    assert request.headers["SmileID-Token"] == "tok"
    assert "User-ID" not in request.headers
    assert "SmileID-Partner-ID" not in request.headers
    parts = parse_multipart(request)
    by_name = {p["name"]: p for p in parts}
    assert part_names(parts) == [
        "user_id",
        "callback_url",
        "address",
        "country",
        "id_number",
        "utility_number",
        "utility_provider",
        "utility_type",
        "user_details",
        "consent",
        "partner_params",
        "metadata",
    ]
    assert by_name["address"]["body"] == b"12 Test Road, Testville"
    assert by_name["address"]["content_type"] is None
    assert by_name["country"]["body"] == b"NG"
    assert by_name["id_number"]["body"] == b"9001015800085"
    assert by_name["utility_number"]["body"] == b"0123456789"
    assert by_name["utility_provider"]["body"] == b"IKEDC"
    assert by_name["utility_type"]["body"] == b"PrePaid"
    assert by_name["user_id"]["body"] == b"user-1"
    assert by_name["callback_url"]["body"] == b"https://example.com/callback"
    assert json.loads(by_name["user_details"]["body"]) == user_details_dict()
    assert by_name["user_details"]["content_type"] == "application/json"
    assert json.loads(by_name["consent"]["body"]) == consent_dict()
    assert json.loads(by_name["partner_params"]["body"]) == {"order_id": "1"}
    assert json.loads(by_name["metadata"]["body"]) == [{"name": "k", "value": "v"}]


def test_address_verification_minimal_request_and_default_callback(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/address").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    make_client(default_callback_url="https://example.com/default").address.verify(
        address="1 Road",
        country="ZA",
        id_number="9001015800085",
        user_details=usesmileid.UserDetails("A", "B", email="a@example.com"),
        consent=usesmileid.Consent.granted(
            granted_at=datetime(2026, 3, 6, tzinfo=timezone.utc),
            notice_language="EN",
            notice_privacy_policy_url="https://example.com/privacy",
        ),
    )
    assert _claims(mock_token.calls.last.request) == {"product": "address_verification"}
    by_name = {p["name"]: p for p in parse_multipart(route.calls.last.request)}
    assert sorted(by_name) == [
        "address",
        "callback_url",
        "consent",
        "country",
        "id_number",
        "user_details",
    ]
    assert by_name["callback_url"]["body"] == b"https://example.com/default"


def test_address_verification_400_is_a_typed_error(respx_mock: Any, mock_token: Any) -> None:
    respx_mock.post(f"{BASE_URL}/v3/address").mock(
        return_value=httpx.Response(
            400,
            json={
                "status": "Bad Request",
                "message": "Either 'id_number' or 'utility_number' is required.",
            },
        )
    )
    with pytest.raises(SmileIDError) as err:
        make_client().address.verify(
            address="1 Road",
            country="NG",
            user_details=user_details_dict(),
            consent=consent_dict(),
        )
    assert err.value.status_code == 400
    assert "utility_number" in str(err.value)


def test_address_verification_rejects_invalid_user_details(respx_mock: Any) -> None:
    with pytest.raises(ValidationError):
        make_client().address.verify(
            address="1 Road",
            country="NG",
            user_details={"given_names": "A"},
            consent=consent_dict(),
        )


# -- phone ---------------------------------------------------------------


def test_phone_verification_golden_request(respx_mock: Any) -> None:
    token = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    route = respx_mock.post(f"{BASE_URL}/v3/phone").mock(
        return_value=httpx.Response(
            202, json={**ACCEPTED, "created_at": "2026-03-10T12:00:00.000Z"}
        )
    )
    accepted = make_client().phone.verify(
        country="GH",
        phone_number="+233201234567",
        operator="MTN",
        id_number="GHA-1",
        user_details=user_details_dict(),
        consent=consent_dict(),
        user_id="user-2",
        callback_url="https://example.com/callback",
        partner_params={"a": "b"},
        metadata=[{"name": "k", "value": "v"}],
    )
    assert accepted.is_accepted
    assert accepted.created_at == "2026-03-10T12:00:00.000Z"
    assert _claims(token.calls.last.request) == {
        "user_id": "user-2",
        "product": "phone_number_verification",
    }
    request = route.calls.last.request
    assert request.headers["SmileID-Token"] == "tok"
    assert "User-ID" not in request.headers
    parts = parse_multipart(request)
    by_name = {p["name"]: p for p in parts}
    assert part_names(parts) == [
        "user_id",
        "callback_url",
        "country",
        "phone_number",
        "operator",
        "id_number",
        "user_details",
        "consent",
        "partner_params",
        "metadata",
    ]
    assert by_name["country"]["body"] == b"GH"
    assert by_name["phone_number"]["body"] == b"+233201234567"
    assert by_name["operator"]["body"] == b"MTN"
    assert by_name["id_number"]["body"] == b"GHA-1"
    assert by_name["user_id"]["body"] == b"user-2"
    assert json.loads(by_name["consent"]["body"]) == consent_dict()
    assert json.loads(by_name["user_details"]["body"]) == user_details_dict()
    assert json.loads(by_name["metadata"]["body"]) == [{"name": "k", "value": "v"}]
    assert json.loads(by_name["partner_params"]["body"]) == {"a": "b"}


def test_phone_verification_minimal_request(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/phone").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    make_client().phone.verify(
        country="NG",
        phone_number="+2348012345678",
        user_details=user_details_dict(),
        consent=consent_dict(),
    )
    assert _claims(mock_token.calls.last.request) == {"product": "phone_number_verification"}
    names = part_names(parse_multipart(route.calls.last.request))
    assert names == ["country", "phone_number", "user_details", "consent"]


def test_phone_verification_403_is_a_typed_error(respx_mock: Any, mock_token: Any) -> None:
    respx_mock.post(f"{BASE_URL}/v3/phone").mock(
        return_value=httpx.Response(403, json={"status": "Forbidden", "message": "No"})
    )
    with pytest.raises(SmileIDError) as err:
        make_client().phone.verify(
            country="NG",
            phone_number="+2348012345678",
            user_details=user_details_dict(),
            consent=consent_dict(),
        )
    assert err.value.status_code == 403


# -- Smile Links ---------------------------------------------------------


def test_create_smile_link_golden_request(respx_mock: Any) -> None:
    token = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    route = respx_mock.post(f"{BASE_URL}/v3/smile_links").mock(
        return_value=httpx.Response(
            201,
            json={
                "link": LINK["link"],
                "message": "Smile Link created",
                "ref_id": REF_ID,
                "user_id": "user-123",
            },
        )
    )
    created = make_client().smile_links.create(
        id_types=ID_TYPES,
        name="Onboarding",
        company_name="Acme Pay",
        notice_privacy_policy_url="https://partner.example/privacy",
        is_single_use=True,
        callback_url="https://partner.example/callback",
        description="KYC",
        expires_at=datetime(2026, 12, 1, 9, 30, tzinfo=timezone.utc),
        logo_url="https://partner.example/logo.png",
        redirect_url="https://partner.example/done",
        theme_color="#0a0a0a",
        partner_params={"k": "v"},
        user_id="user-123",
    )
    assert isinstance(created, usesmileid.SmileLinkCreated)
    assert created.ref_id == REF_ID
    assert created.link == LINK["link"]
    assert created.message == "Smile Link created"
    assert created.user_id == "user-123"

    # No product claim and no user_id claim: the token has no body at all.
    assert token.calls.last.request.content == b""
    request = route.calls.last.request
    assert request.headers["SmileID-Token"] == "tok"
    assert "User-ID" not in request.headers
    parts = parse_multipart(request)
    by_name = {p["name"]: p for p in parts}
    assert part_names(parts) == [
        "name",
        "company_name",
        "notice_privacy_policy_url",
        "is_single_use",
        "callback_url",
        "description",
        "expires_at",
        "logo_url",
        "redirect_url",
        "theme_color",
        "user_id",
        "id_types",
        "partner_params",
    ]
    assert by_name["id_types"]["content_type"] == "application/json"
    assert json.loads(by_name["id_types"]["body"]) == ID_TYPES
    assert by_name["is_single_use"]["body"] == b"true"
    assert by_name["is_single_use"]["content_type"] is None
    assert by_name["expires_at"]["body"] == b"2026-12-01T09:30:00+00:00"
    assert by_name["partner_params"]["content_type"] == "application/json"
    assert json.loads(by_name["partner_params"]["body"]) == {"k": "v"}
    assert by_name["name"]["body"] == b"Onboarding"
    assert by_name["company_name"]["body"] == b"Acme Pay"
    assert by_name["user_id"]["body"] == b"user-123"
    assert by_name["theme_color"]["body"] == b"#0a0a0a"


def test_create_smile_link_minimal_request_and_multi_use_result(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/smile_links").mock(
        return_value=httpx.Response(
            201,
            json={
                "link": "https://l",
                "message": "Smile Link created",
                "ref_id": REF_ID,
                "user_id": None,
            },
        )
    )
    created = make_client(default_callback_url="https://example.com/default").smile_links.create(
        id_types=ID_TYPES,
        name="Onboarding",
        notice_privacy_policy_url="https://partner.example/privacy",
        is_single_use=False,
        expires_at="2026-12-01T00:00:00Z",
    )
    assert created.user_id is None
    by_name = {p["name"]: p for p in parse_multipart(route.calls.last.request)}
    assert sorted(by_name) == [
        "callback_url",
        "expires_at",
        "id_types",
        "is_single_use",
        "name",
        "notice_privacy_policy_url",
    ]
    assert by_name["is_single_use"]["body"] == b"false"
    assert by_name["expires_at"]["body"] == b"2026-12-01T00:00:00Z"
    assert by_name["callback_url"]["body"] == b"https://example.com/default"


def test_create_smile_link_409_is_a_typed_error_and_is_not_retried(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/smile_links").mock(
        return_value=httpx.Response(
            409, json={"status": "Conflict", "message": "User ID is taken."}
        )
    )
    with pytest.raises(SmileIDError) as err:
        make_client().smile_links.create(
            id_types=ID_TYPES,
            name="n",
            notice_privacy_policy_url="https://p",
            is_single_use=True,
        )
    assert err.value.status_code == 409
    assert route.call_count == 1

    route.mock(return_value=httpx.Response(500, json={"status": "Server Error", "message": "x"}))
    with pytest.raises(SmileIDError):
        make_client().smile_links.create(
            id_types=ID_TYPES,
            name="n",
            notice_privacy_policy_url="https://p",
            is_single_use=True,
        )
    assert route.call_count == 2  # a create is never retried


def test_list_smile_links_request_and_response(respx_mock: Any) -> None:
    token = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    route = respx_mock.get(f"{BASE_URL}/v3/smile_links").mock(
        return_value=httpx.Response(
            200,
            json={
                "links": [{**LINK, **STATS}],
                "meta": {"current_page": 2, "limit": 5, "total_count": 11, "total_pages": 3},
            },
        )
    )
    result = make_client().smile_links.list(limit=5, page=2, single_use=False)

    assert token.calls.last.request.content == b""
    request = route.calls.last.request
    assert request.headers["SmileID-Token"] == "tok"
    assert dict(request.url.params) == {"limit": "5", "page": "2", "single_use": "false"}
    assert not request.content
    assert isinstance(result, usesmileid.SmileLinkListResponse)
    assert result.meta.current_page == 2
    assert result.meta.limit == 5
    assert result.meta.total_count == 11
    assert result.meta.total_pages == 3
    [item] = result.links
    assert item.ref_id == REF_ID
    assert item.id_types[0].verification_method == "enhanced_kyc"
    assert item.clear == 12
    assert item.block == 1
    assert item.attention == 2
    assert item.error == 0
    assert item.successful_jobs == 14
    assert item.failed_jobs == 1
    assert item.total_jobs == 15


def test_list_smile_links_defaults_send_no_query_and_single_use_true(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.get(f"{BASE_URL}/v3/smile_links").mock(
        return_value=httpx.Response(
            200,
            json={
                "links": [],
                "meta": {"current_page": 1, "limit": 20, "total_count": 0, "total_pages": 0},
            },
        )
    )
    assert make_client().smile_links.list().links == []
    assert dict(route.calls.last.request.url.params) == {}
    make_client().smile_links.list(single_use=True)
    assert dict(route.calls.last.request.url.params) == {"single_use": "true"}


def test_list_smile_links_is_retried_on_a_transient_error(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.get(f"{BASE_URL}/v3/smile_links").mock(
        side_effect=[
            httpx.Response(500, json={"status": "Internal Server Error", "message": "x"}),
            httpx.Response(
                200,
                json={
                    "links": [],
                    "meta": {"current_page": 1, "limit": 20, "total_count": 0, "total_pages": 0},
                },
            ),
        ]
    )
    make_client().smile_links.list()
    assert route.call_count == 2


def test_get_smile_link_request_and_response(respx_mock: Any) -> None:
    token = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    route = respx_mock.get(f"{BASE_URL}/v3/smile_links/{REF_ID}").mock(
        return_value=httpx.Response(200, json=LINK)
    )
    link = make_client().smile_links.get(REF_ID)

    assert token.calls.last.request.content == b""
    assert route.calls.last.request.headers["SmileID-Token"] == "tok"
    assert isinstance(link, usesmileid.SmileLinkResource)
    assert link.ref_id == REF_ID
    assert link.link == LINK["link"]
    assert link.name == "Onboarding"
    assert link.company_name == "Acme Pay"
    assert link.description is None
    assert link.id_types[0].country == "NG"
    assert link.id_types[0].id_type == "NIN"
    assert link.is_single_use is False
    assert link.callback_url == "https://partner.example/callback"
    assert link.theme_color == "#000"
    assert link.token_provided_fields == ["country", "id_type"]
    assert link.token_provided_values == {"country": "NG", "id_type": "NIN"}
    assert link.created_at == "2024-01-15T10:30:00Z"
    assert link.model_extra == {"extra_field": 1}


def test_get_smile_link_404_is_a_typed_error_and_the_id_is_quoted(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.get(f"{BASE_URL}/v3/smile_links/a%2Fb").mock(
        return_value=httpx.Response(404, json={"status": "Not Found", "message": "Link not found"})
    )
    with pytest.raises(SmileIDError) as err:
        make_client().smile_links.get("a/b")
    assert err.value.status_code == 404
    assert route.call_count == 1


def test_update_smile_link_golden_request(respx_mock: Any) -> None:
    token = respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"token": "tok"})
    )
    route = respx_mock.put(f"{BASE_URL}/v3/smile_links/{REF_ID}").mock(
        return_value=httpx.Response(200, json={**LINK, "disabled_at": "2024-02-01T00:00:00Z"})
    )
    link = make_client().smile_links.update(REF_ID, id_types=ID_TYPES, is_disabled=True)

    assert token.calls.last.request.content == b""
    request = route.calls.last.request
    assert request.method == "PUT"
    assert request.headers["SmileID-Token"] == "tok"
    parts = parse_multipart(request)
    by_name = {p["name"]: p for p in parts}
    assert part_names(parts) == ["is_disabled", "id_types"]
    assert by_name["id_types"]["content_type"] == "application/json"
    assert json.loads(by_name["id_types"]["body"]) == ID_TYPES
    assert by_name["is_disabled"]["body"] == b"true"
    assert by_name["is_disabled"]["content_type"] is None
    assert link.disabled_at == "2024-02-01T00:00:00Z"


@pytest.mark.parametrize(
    ("kwargs", "names"),
    [
        ({"is_disabled": False}, ["is_disabled"]),
        ({"id_types": ID_TYPES}, ["id_types"]),
    ],
)
def test_update_smile_link_sends_only_given_fields(
    respx_mock: Any, mock_token: Any, kwargs: Any, names: Any
) -> None:
    route = respx_mock.put(f"{BASE_URL}/v3/smile_links/{REF_ID}").mock(
        return_value=httpx.Response(200, json=LINK)
    )
    make_client().smile_links.update(REF_ID, **kwargs)
    assert part_names(parse_multipart(route.calls.last.request)) == names


def test_update_smile_link_requires_a_field_and_sends_nothing(respx_mock: Any) -> None:
    with pytest.raises(ValidationError):
        make_client().smile_links.update(REF_ID)
    assert respx_mock.calls.call_count == 0


@pytest.mark.parametrize("status", [409, 410])
def test_update_smile_link_errors_are_typed(
    respx_mock: Any, mock_token: Any, status: int
) -> None:
    respx_mock.put(f"{BASE_URL}/v3/smile_links/{REF_ID}").mock(
        return_value=httpx.Response(status, json={"status": "Conflict", "message": "no"})
    )
    with pytest.raises(SmileIDError) as err:
        make_client().smile_links.update(REF_ID, is_disabled=True)
    assert err.value.status_code == status


# -- sync response headers ----------------------------------------------

_HEADERS = {
    "SmileID-Job-ID": "job_from_header",
    "User-ID": "user_from_header",
    "Response-Signature": "c2lnbmF0dXJl",
    "Response-Timestamp": "2026-03-10T12:00:04.000Z",
}


@pytest.mark.parametrize("product", ["basic", "aml"])
def test_sync_results_expose_every_response_header(
    respx_mock: Any, mock_token: Any, product: str
) -> None:
    body = {"status": "clear", "message": "ok", "job_id": "job_body", "user_id": "user_body"}
    client = make_client()
    if product == "basic":
        route = respx_mock.post(f"{BASE_URL}/v3/basic_kyc/sync")

        def call() -> Any:
            return client.basic_kyc.verify_sync(
                country="NG",
                id_type="NIN",
                id_number="1",
                user_details=user_details_dict(),
                consent=consent_dict(),
            )

    else:
        route = respx_mock.post(f"{BASE_URL}/v3/aml/sync")

        def call() -> Any:
            return client.aml.screen_sync(
                countries=["NG"],
                full_name="A B",
                user_details=user_details_dict(),
                consent=consent_dict(),
            )

    route.mock(return_value=httpx.Response(200, json=body, headers=_HEADERS))
    result = call()
    assert result.job_id == "job_from_header"
    assert result.user_id == "user_from_header"
    assert result.response_signature == "c2lnbmF0dXJl"
    assert result.response_timestamp == "2026-03-10T12:00:04.000Z"

    # Without the headers: ids fall back to the body, the signature is absent.
    route.mock(
        return_value=httpx.Response(
            200, json={**body, "response_signature": "from_body"}, headers={"User-ID": "  "}
        )
    )
    result = call()
    assert result.job_id == "job_body"
    assert result.user_id == "user_body"
    assert result.response_signature is None
    assert result.response_timestamp is None
