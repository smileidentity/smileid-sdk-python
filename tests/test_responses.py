"""Matrix item 5: response parsing and AcceptedResponse normalization."""

from __future__ import annotations

from typing import Any

import httpx

from tests.conftest import BASE_URL, consent_dict, make_client, user_details_dict
from usesmileid.generated.models import AcceptedResponse, JobStatus


def test_is_accepted_normalizes_capitalized_status() -> None:
    response = AcceptedResponse.model_validate(
        {
            "status": "Accepted",
            "message": "Request accepted and queued for processing.",
            "job_id": "job_01h8x9y2z3a4b5c6d7e8f9g0h1",
            "user_id": "user_01h8x9y2z3a4b5c6d7e8f9g0h1",
        }
    )
    assert response.is_accepted is True
    assert response.status == "Accepted"  # raw value preserved


def test_is_accepted_normalizes_lowercase_status() -> None:
    response = AcceptedResponse.model_validate(
        {
            "status": "accepted",
            "message": "Request accepted and queued for processing.",
            "job_id": "job_01h8x9y2z3a4b5c6d7e8f9g0h1",
            "user_id": "user_01h8x9y2z3a4b5c6d7e8f9g0h1",
            "created_at": "2026-03-10T12:00:00.000Z",
        }
    )
    assert response.is_accepted is True
    assert response.created_at == "2026-03-10T12:00:00.000Z"


def test_is_accepted_false_for_other_status() -> None:
    response = AcceptedResponse.model_validate({"status": "rejected"})
    assert response.is_accepted is False


def test_is_complete_true_for_every_decision() -> None:
    for decision in ("clear", "block", "attention", "error"):
        assert JobStatus.model_validate({"status": decision}).is_complete is True


def test_is_complete_false_while_pending() -> None:
    for pending in ("processing", "not_found"):
        assert JobStatus.model_validate({"status": pending}).is_complete is False


def test_is_complete_false_for_empty_status() -> None:
    # A truncated response must not stop a poller with no decision to report.
    assert JobStatus.model_validate({"status": ""}).is_complete is False


def test_golden_enhanced_kyc_success_parsing(respx_mock: Any, mock_token: Any) -> None:
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(
            202,
            json={
                "status": "Accepted",
                "message": "Request accepted and queued for processing.",
                "job_id": "job_01h8x9y2z3a4b5c6d7e8f9g0h1",
                "user_id": "user_01h8x9y2z3a4b5c6d7e8f9g0h1",
            },
        )
    )
    client = make_client()
    accepted = client.enhanced_kyc.verify(
        country="NG",
        id_type="NIN",
        id_number="12345678901",
        user_details=user_details_dict(),
        consent=consent_dict(),
    )
    assert accepted.is_accepted
    assert accepted.job_id == "job_01h8x9y2z3a4b5c6d7e8f9g0h1"
    assert accepted.user_id == "user_01h8x9y2z3a4b5c6d7e8f9g0h1"
    assert accepted.message == "Request accepted and queued for processing."


def test_golden_services_response_parsing(respx_mock: Any, mock_token: Any) -> None:
    respx_mock.get(f"{BASE_URL}/v3/services/bank_codes").mock(
        return_value=httpx.Response(
            200,
            json={"bank_codes": [{"code": "044", "country": "NG", "name": "Access Bank"}]},
        )
    )
    respx_mock.get(f"{BASE_URL}/v3/services/supported_id_types").mock(
        return_value=httpx.Response(
            200,
            json={
                "id_types": [
                    {
                        "country": "NG",
                        "label": "Bank Verification Number",
                        "regex": "^\\d{11}$",
                        "required_fields": ["first_name", "last_name", "dob"],
                        "type": "BVN",
                    },
                    {
                        "bank_code": "044",
                        "country": "NG",
                        "label": "Bank Account (Access Bank)",
                        "regex": "^\\d{10}$",
                        "required_fields": ["first_name", "last_name"],
                        "type": "BANK_ACCOUNT",
                    },
                ]
            },
        )
    )
    respx_mock.get(f"{BASE_URL}/v3/services/supported_documents").mock(
        return_value=httpx.Response(
            200,
            json={
                "valid_documents": [
                    {
                        "country": {"code": "NG", "name": "Nigeria", "continent": "AFRICA"},
                        "id_types": [
                            {
                                "code": "DRIVERS_LICENSE",
                                "name": "Driver's License",
                                "example": ["AAA00000AA00"],
                                "has_back": True,
                            }
                        ],
                    }
                ]
            },
        )
    )
    respx_mock.get(f"{BASE_URL}/v3/services/id_status").mock(
        return_value=httpx.Response(
            200,
            json={
                "last_checked": "2026-04-14T12:30:00.000Z",
                "last_check_status": "success",
                "last_hour_success_rate": "95%",
                "last_known_status": "online",
                "last_check_success_rate": "90%",
            },
        )
    )

    client = make_client()
    banks = client.services.bank_codes(country="NG")
    assert banks.bank_codes[0].code == "044"
    assert banks.bank_codes[0].name == "Access Bank"

    id_types = client.services.supported_id_types(country="NG")
    assert id_types.id_types[0].type == "BVN"
    assert id_types.id_types[1].bank_code == "044"

    documents = client.services.supported_documents(country_code="NG")
    doc = documents.valid_documents[0]
    assert doc.country.code == "NG"
    assert doc.id_types[0].has_back is True

    status = client.services.id_status(country="NG", id_type="NIN")
    assert status.last_check_status == "success"
    assert status.last_hour_success_rate == "95%"


def test_replay_and_fraud_response_parsing(respx_mock: Any, mock_token: Any) -> None:
    respx_mock.post(f"{BASE_URL}/v3/replay/job_01h8x9y2z3a4b5c6d7e8f9g0h1").mock(
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
    respx_mock.post(f"{BASE_URL}/v3/users/user-123/report_fraud").mock(
        return_value=httpx.Response(
            202,
            json={"status": "accepted", "message": "Fraud report accepted", "user_id": "user-123"},
        )
    )
    client = make_client()
    replayed = client.verifications.replay("job_01h8x9y2z3a4b5c6d7e8f9g0h1")
    assert replayed.status == "accepted"
    assert replayed.message == "Callback replay queued successfully."

    cleared = client.users.clear_fraud(
        "user-123", notes="Cleared by appeals review", reported_by="risk@partner.example"
    )
    assert cleared.status == "accepted"
    assert cleared.user_id == "user-123"
