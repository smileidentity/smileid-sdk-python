"""Matrix item 6: client-side validation."""

from __future__ import annotations

from typing import Any

import pytest

import usesmileid
from tests.conftest import JPEG_BYTES, LIVENESS, consent_dict, make_client
from usesmileid.helpers.user_details import normalize_user_details


def test_user_details_requires_email_or_phone(respx_mock: Any, mock_token: Any) -> None:
    client = make_client()
    with pytest.raises(usesmileid.errors.ValidationError):
        client.enhanced_kyc.verify(
            country="NG",
            id_type="NIN",
            id_number="12345678901",
            user_details={"given_names": "John", "last_name": "Doe"},
            consent=consent_dict(),
        )
    # Validation error raised before any HTTP call.
    assert not respx_mock.calls


def test_user_details_email_only_ok() -> None:
    data = normalize_user_details(
        {"given_names": "John", "last_name": "Doe", "email": "john@example.com"}
    )
    assert data["email"] == "john@example.com"


def test_user_details_phone_only_ok() -> None:
    data = normalize_user_details(
        {"given_names": "John", "last_name": "Doe", "phone_number": "+2348012345678"}
    )
    assert data["phone_number"] == "+2348012345678"


def test_user_details_missing_names_rejected() -> None:
    with pytest.raises(usesmileid.errors.ValidationError):
        normalize_user_details({"last_name": "Doe", "email": "john@example.com"})
    with pytest.raises(usesmileid.errors.ValidationError):
        normalize_user_details({"given_names": "John", "email": "john@example.com"})


def test_flag_fraud_requires_reason(respx_mock: Any, mock_token: Any) -> None:
    client = make_client()
    with pytest.raises(usesmileid.errors.ValidationError):
        client.users.report_fraud(
            "user-123", is_fraud=True, reported_by="risk@partner.example"
        )
    assert not respx_mock.calls


def test_fraud_reason_other_requires_notes(respx_mock: Any, mock_token: Any) -> None:
    client = make_client()
    with pytest.raises(usesmileid.errors.ValidationError):
        client.users.flag_fraud(
            "user-123", reason="OTHER", reported_by="risk@partner.example"
        )


def test_clear_fraud_requires_notes(respx_mock: Any, mock_token: Any) -> None:
    client = make_client()
    with pytest.raises(usesmileid.errors.ValidationError):
        client.users.report_fraud(
            "user-123", is_fraud=False, reported_by="risk@partner.example"
        )


def test_fraud_unknown_reason_rejected(respx_mock: Any, mock_token: Any) -> None:
    client = make_client()
    with pytest.raises(usesmileid.errors.ValidationError):
        client.users.flag_fraud(
            "user-123", reason="MADE_UP", reported_by="risk@partner.example"
        )


def test_fraud_notes_length_limit(respx_mock: Any, mock_token: Any) -> None:
    client = make_client()
    with pytest.raises(usesmileid.errors.ValidationError):
        client.users.clear_fraud(
            "user-123", notes="x" * 501, reported_by="risk@partner.example"
        )


def test_authenticate_requires_images_unless_enrolled(
    respx_mock: Any, mock_token: Any
) -> None:
    client = make_client()
    user_details = {"given_names": "John", "last_name": "Doe", "email": "john@example.com"}
    with pytest.raises(usesmileid.errors.ValidationError):
        client.biometric.authenticate(
            user_id="user-1", consent=consent_dict(), user_details=user_details
        )
    with pytest.raises(usesmileid.errors.ValidationError):
        client.biometric.authenticate(
            user_id="user-1",
            selfie_image=JPEG_BYTES,  # liveness missing
            consent=consent_dict(),
            user_details=user_details,
        )
    assert not respx_mock.calls


def test_authenticate_use_enrolled_image_skips_image_requirement(
    respx_mock: Any, mock_token: Any
) -> None:
    import httpx

    from tests.conftest import BASE_URL

    route = respx_mock.post(f"{BASE_URL}/v3/authentication").mock(
        return_value=httpx.Response(202, json={"status": "Accepted"})
    )
    client = make_client()
    client.biometric.authenticate(
        user_id="user-1",
        use_enrolled_image=True,
        consent=consent_dict(),
        user_details={"given_names": "John", "last_name": "Doe", "email": "john@example.com"},
    )
    assert route.called


def test_authenticate_with_images_sends_them(respx_mock: Any, mock_token: Any) -> None:
    import httpx

    from tests.conftest import BASE_URL, parse_multipart

    route = respx_mock.post(f"{BASE_URL}/v3/authentication").mock(
        return_value=httpx.Response(202, json={"status": "Accepted"})
    )
    client = make_client()
    client.biometric.authenticate(
        user_id="user-1",
        selfie_image=JPEG_BYTES,
        liveness_images=LIVENESS,
        consent=consent_dict(),
        user_details={"given_names": "John", "last_name": "Doe", "email": "john@example.com"},
    )
    parts = parse_multipart(route.calls.last.request)
    names = [p["name"] for p in parts]
    assert "selfie_image" in names
    assert names.count("liveness_images") == 6


def test_client_config_validation() -> None:
    with pytest.raises(usesmileid.errors.ValidationError):
        usesmileid.Client(partner_id="0123", api_key="k")  # leading zero
    with pytest.raises(usesmileid.errors.ValidationError):
        usesmileid.Client(partner_id="1234", api_key="")
    with pytest.raises(usesmileid.errors.ValidationError):
        usesmileid.Client(partner_id="1234", api_key="k", environment="staging")


def test_verify_enhanced_requires_id_type(respx_mock: Any, mock_token: Any) -> None:
    client = make_client()
    with pytest.raises(usesmileid.errors.ValidationError):
        client.documents.verify_enhanced(
            selfie_image=JPEG_BYTES,
            liveness_images=LIVENESS,
            document=JPEG_BYTES,
            consent=consent_dict(),
            country="NG",
            id_type="",
            user_details={"given_names": "John", "last_name": "Doe", "email": "john@example.com"},
        )
