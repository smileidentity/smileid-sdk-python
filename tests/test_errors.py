"""Matrix item 4: error hierarchy over both wire shapes."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

import smileid
from tests.conftest import BASE_URL, consent_dict, make_client, user_details_dict


def _verify(client: smileid.Client) -> Any:
    return client.enhanced_kyc.verify(
        country="NG",
        id_type="NIN",
        id_number="12345678901",
        user_details=user_details_dict(),
        consent=consent_dict(),
    )


def test_400_status_message_shape(respx_mock: Any, mock_token: Any) -> None:
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(
            400,
            json={
                "status": "Bad Request",
                "message": "Either email or phone_number is required.",
            },
        )
    )
    client = make_client()
    with pytest.raises(smileid.errors.InvalidRequestError) as excinfo:
        _verify(client)
    err = excinfo.value
    assert err.status_code == 400
    assert err.status == "Bad Request"
    assert err.message == "Either email or phone_number is required."
    assert err.code is None
    assert err.raw_body is not None and "phone_number" in err.raw_body


def test_402_payment_required(respx_mock: Any, mock_token: Any) -> None:
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(
            402,
            json={"status": "Payment Required", "message": "Insufficient wallet balance."},
        )
    )
    client = make_client()
    with pytest.raises(smileid.errors.PaymentRequiredError) as excinfo:
        _verify(client)
    assert excinfo.value.message == "Insufficient wallet balance."


def test_413_payload_too_large(respx_mock: Any, mock_token: Any) -> None:
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(
            413,
            json={"status": "Content Too Large", "message": "selfie_image is too large."},
        )
    )
    client = make_client()
    with pytest.raises(smileid.errors.PayloadTooLargeError):
        _verify(client)


def test_services_error_code_shape(respx_mock: Any) -> None:
    """The {error, code} shape on unauthenticated services endpoints."""
    respx_mock.get(f"{BASE_URL}/v3/services/bank_codes").mock(
        return_value=httpx.Response(
            403,
            json={"error": "You are not authorized to do that.", "code": "2413"},
        )
    )
    client = make_client()
    with pytest.raises(smileid.errors.PermissionError) as excinfo:
        client.services.bank_codes()
    err = excinfo.value
    assert err.status_code == 403
    assert err.message == "You are not authorized to do that."
    assert err.code == "2413"
    assert err.status is None  # no status text in the {error, code} shape


def test_id_status_message_status_ordering(respx_mock: Any, mock_token: Any) -> None:
    """id_status reorders keys to {message, status}; same parsing rules apply."""
    respx_mock.get(f"{BASE_URL}/v3/services/id_status").mock(
        return_value=httpx.Response(
            400, json={"message": '"country" is required', "status": "Bad Request"}
        )
    )
    client = make_client()
    with pytest.raises(smileid.errors.InvalidRequestError) as excinfo:
        client.services.id_status(country="", id_type="NIN")
    assert excinfo.value.message == '"country" is required'
    assert excinfo.value.status == "Bad Request"


def test_non_json_body_falls_back_to_reason_phrase(
    respx_mock: Any, mock_token: Any
) -> None:
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(502, text="<html>Bad Gateway</html>")
    )
    client = make_client()
    with pytest.raises(smileid.errors.APIError) as excinfo:
        _verify(client)
    assert excinfo.value.status_code == 502
    assert excinfo.value.message  # falls back to the reason phrase
    assert excinfo.value.raw_body == "<html>Bad Gateway</html>"


def test_retrieve_404_returns_not_found_jobstatus_not_error(
    respx_mock: Any, mock_token: Any
) -> None:
    """404 from status returns a JobStatus, never NotFoundError."""
    respx_mock.get(f"{BASE_URL}/v3/status/job_missing").mock(
        return_value=httpx.Response(
            404,
            json={
                "status": "not_found",
                "job_id": "job_missing",
                "user_id": "unknown",
                "message": "Verification not found",
            },
        )
    )
    client = make_client()
    status = client.verifications.retrieve("job_missing")
    assert status.status == "not_found"
    assert status.is_not_found
    assert status.message == "Verification not found"


def test_replay_404_still_raises_not_found(respx_mock: Any, mock_token: Any) -> None:
    """Only verifications.retrieve treats 404 specially; replay raises."""
    respx_mock.post(f"{BASE_URL}/v3/replay/job_missing").mock(
        return_value=httpx.Response(
            404, json={"status": "Not Found", "message": "Verification not found"}
        )
    )
    client = make_client()
    with pytest.raises(smileid.errors.NotFoundError):
        client.verifications.replay("job_missing")


def test_429_rate_limit(respx_mock: Any, mock_token: Any) -> None:
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(
            429, json={"status": "Too Many Requests", "message": "Slow down"}
        )
    )
    client = make_client()
    with pytest.raises(smileid.errors.RateLimitError):
        _verify(client)


def test_error_hierarchy_all_subclass_base() -> None:
    for klass in (
        smileid.errors.InvalidRequestError,
        smileid.errors.AuthenticationError,
        smileid.errors.PaymentRequiredError,
        smileid.errors.PermissionError,
        smileid.errors.NotFoundError,
        smileid.errors.ConflictError,
        smileid.errors.PayloadTooLargeError,
        smileid.errors.RateLimitError,
        smileid.errors.APIError,
        smileid.errors.ConnectionError,
        smileid.errors.TimeoutError,
        smileid.errors.ValidationError,
    ):
        assert issubclass(klass, smileid.errors.SmileIDError)
    assert issubclass(smileid.errors.ValidationError, smileid.errors.InvalidRequestError)
