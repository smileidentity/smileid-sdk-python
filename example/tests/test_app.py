from __future__ import annotations

import base64
import json
from io import StringIO
from typing import Dict, List

import httpx
import pytest

from smileid_example.app import UsageError, run


def test_services_lists_reference_data_without_authentication() -> None:
    fake = FakeSmileAPI()
    out = StringIO()
    run(
        ["--base-url", "https://api.test", "services", "--country", "NG"],
        getenv=example_env,
        stdout=out,
        http_client=fake.client,
    )

    result = json.loads(out.getvalue())
    assert result["country"] == "NG"
    assert result["bank_codes"][0]["code"] == "001"
    assert result["id_types"][0]["type"] == "NIN"
    assert fake.token_calls == 0


def test_enhanced_kyc_submits_verification() -> None:
    fake = FakeSmileAPI()
    out = StringIO()
    run(
        [
            "--base-url",
            "https://api.test",
            "--callback-url",
            "https://example.com/smile-callback",
            "enhanced-kyc",
            "--country",
            "NG",
            "--id-type",
            "NIN",
            "--id-number",
            "12345678901",
            "--given-names",
            "Amina",
            "--last-name",
            "Okafor",
            "--email",
            "amina@example.com",
        ],
        getenv=example_env,
        stdout=out,
        http_client=fake.client,
    )

    result = json.loads(out.getvalue())
    assert result["job_id"] == "job_enhanced_123"
    assert result["accepted"] is True
    assert fake.token_calls == 1
    request = fake.request_for("/v3/enhanced_kyc")
    body = request.content.decode()
    assert 'name="country"\r\n\r\nNG' in body
    assert 'name="id_type"\r\n\r\nNIN' in body
    assert 'name="callback_url"\r\n\r\nhttps://example.com/smile-callback' in body
    assert '"given_names":"Amina"' in body


def test_status_retrieves_verification() -> None:
    fake = FakeSmileAPI()
    out = StringIO()
    run(
        ["--base-url", "https://api.test", "status", "--job-id", "job_enhanced_123"],
        getenv=example_env,
        stdout=out,
        http_client=fake.client,
    )

    result = json.loads(out.getvalue())
    assert result["status"] == "complete"
    assert result["message"] == "clear"


def test_replay_requests_callback_replay() -> None:
    fake = FakeSmileAPI()
    out = StringIO()
    run(
        [
            "--base-url",
            "https://api.test",
            "replay",
            "--job-id",
            "job_enhanced_123",
            "--callback-url",
            "https://example.com/replay-callback",
        ],
        getenv=example_env,
        stdout=out,
        http_client=fake.client,
    )

    result = json.loads(out.getvalue())
    assert result["status"] == "success"
    assert result["job_id"] == "job_enhanced_123"
    request = fake.request_for("/v3/replay/job_enhanced_123")
    assert request.headers["content-type"].startswith("multipart/form-data")
    assert b'name="callback_url"' in request.content
    assert b"https://example.com/replay-callback" in request.content


def test_help_does_not_require_credentials() -> None:
    out = StringIO()
    run(["help"], getenv=lambda _key: None, stdout=out)
    assert "Usage:" in out.getvalue()


def test_missing_credentials_returns_usage_error() -> None:
    with pytest.raises(UsageError, match="SMILE_PARTNER_ID"):
        run(["services"], getenv=lambda _key: None, stdout=StringIO())


def example_env(key: str) -> str:
    return {"SMILE_PARTNER_ID": "12345", "SMILE_API_KEY": "test-api-key"}.get(key, "")


class FakeSmileAPI:
    def __init__(self) -> None:
        self.requests: List[httpx.Request] = []
        self.token_calls = 0
        self.client = httpx.Client(transport=httpx.MockTransport(self.handle))

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/v3/token":
            self.token_calls += 1
            assert request.headers["smileid-partner-id"] == "12345"
            assert request.headers["smileid-api-key"] == "test-api-key"
            return response(200, {"token": make_jwt()})
        if path == "/v3/services/bank_codes":
            assert request.url.params["country"] == "NG"
            return response(
                200,
                {"bank_codes": [{"code": "001", "country": "NG", "name": "Example Bank"}]},
            )
        if path == "/v3/services/supported_id_types":
            assert request.url.params["country"] == "NG"
            return response(
                200,
                {
                    "id_types": [
                        {
                            "country": "NG",
                            "label": "National Identification Number",
                            "regex": "^\\d{11}$",
                            "required_fields": ["id_number"],
                            "type": "NIN",
                        }
                    ]
                },
            )
        if path == "/v3/services/supported_documents":
            assert request.url.params["country_code"] == "NG"
            return response(
                200,
                {
                    "valid_documents": [
                        {
                            "country": {
                                "code": "NG",
                                "name": "Nigeria",
                                "continent": "Africa",
                            },
                            "id_types": [
                                {
                                    "code": "PASSPORT",
                                    "name": "Passport",
                                    "example": ["A12345678"],
                                    "has_back": False,
                                }
                            ],
                        }
                    ]
                },
            )
        if path == "/v3/enhanced_kyc":
            assert request.headers["smileid-token"].startswith("eyJ")
            return response(
                202,
                {
                    "status": "Accepted",
                    "message": "submitted",
                    "job_id": "job_enhanced_123",
                    "user_id": "user_123",
                },
            )
        if path == "/v3/status/job_enhanced_123":
            assert request.headers["smileid-token"].startswith("eyJ")
            return response(
                200,
                {
                    "status": "complete",
                    "message": "clear",
                    "job_id": "job_enhanced_123",
                    "user_id": "user_123",
                },
            )
        if path == "/v3/replay/job_enhanced_123":
            assert request.headers["smileid-token"].startswith("eyJ")
            return response(
                200,
                {
                    "status": "success",
                    "message": "replayed",
                    "job_id": "job_enhanced_123",
                    "user_id": "user_123",
                },
            )
        return response(404, {"status": "not_found", "message": path})

    def request_for(self, path: str) -> httpx.Request:
        for request in self.requests:
            if request.url.path == path:
                return request
        raise AssertionError(f"no request for {path}")


def response(status: int, body: Dict[str, object]) -> httpx.Response:
    return httpx.Response(status, json=body)


def make_jwt() -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(b'{"exp":4102444800}').rstrip(b"=").decode()
    return f"{header}.{payload}.signature"
