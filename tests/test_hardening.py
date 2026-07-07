"""Fleet hardening: https-only URLs, response-shape guard, path encoding,
multipart header-injection safety."""

from __future__ import annotations

import inspect
import io
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
    user_details_dict,
)
from usesmileid.client.transport import _check_media_type, _sanitize_filename

ACCEPTED = {"status": "Accepted", "job_id": "job_x", "user_id": "user_x"}


def _verify(client: usesmileid.Client, **overrides: Any) -> Any:
    kwargs: Any = {
        "country": "NG",
        "id_type": "NIN",
        "id_number": "12345678901",
        "user_details": user_details_dict(),
        "consent": consent_dict(),
    }
    kwargs.update(overrides)
    return client.enhanced_kyc.verify(**kwargs)


# -- https-only base_url -----------------------------------------------------


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.example.com",
        "ftp://api.example.com",
        "//api.example.com",
        "/relative",
        "api.example.com",
        "https://api.example.com?x=1",
        "https://api.example.com#frag",
        "https://",
    ],
)
def test_base_url_must_be_clean_https(base_url: str) -> None:
    with pytest.raises(usesmileid.errors.ValidationError):
        make_client(base_url=base_url)


def test_https_base_url_accepted() -> None:
    client = make_client(base_url="https://sandbox-proxy.example.com/")
    assert client.config.base_url == "https://sandbox-proxy.example.com"


def test_no_insecure_escape_hatch() -> None:
    """The https requirement is deliberate policy: no bypass option exists."""
    params = inspect.signature(usesmileid.Client.__init__).parameters
    assert not any("insecure" in name for name in params)


# -- https-only callback URLs ------------------------------------------------


def test_default_callback_url_must_be_https() -> None:
    with pytest.raises(usesmileid.errors.ValidationError):
        make_client(default_callback_url="http://app.example.com/cb")


def test_per_request_callback_url_must_be_https_entry_op(
    respx_mock: Any, mock_token: Any
) -> None:
    client = make_client()
    with pytest.raises(usesmileid.errors.ValidationError):
        _verify(client, callback_url="http://app.example.com/cb")
    assert not respx_mock.calls  # rejected before any request, even the token


def test_per_request_callback_url_must_be_https_replay(
    respx_mock: Any, mock_token: Any
) -> None:
    client = make_client()
    with pytest.raises(usesmileid.errors.ValidationError):
        client.verifications.replay("job_x", callback_url="http://app.example.com/cb")
    assert not respx_mock.calls


def test_https_callback_url_still_sent(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(202, json=ACCEPTED)
    )
    client = make_client(default_callback_url="https://app.example.com/cb")
    _verify(client)
    parts = parse_multipart(route.calls.last.request)
    callback = next(p for p in parts if p["name"] == "callback_url")
    assert callback["body"] == b"https://app.example.com/cb"


# -- UnexpectedResponseError -------------------------------------------------


def test_2xx_non_json_body_raises_unexpected_response(
    respx_mock: Any, mock_token: Any
) -> None:
    respx_mock.post(f"{BASE_URL}/v3/enhanced_kyc").mock(
        return_value=httpx.Response(202, text="OK")
    )
    client = make_client()
    with pytest.raises(usesmileid.errors.UnexpectedResponseError) as excinfo:
        _verify(client)
    err = excinfo.value
    assert err.status_code == 202
    assert err.raw_body == "OK"
    assert isinstance(err, usesmileid.errors.SmileIDError)


def test_2xx_json_array_body_raises_unexpected_response(respx_mock: Any) -> None:
    respx_mock.get(f"{BASE_URL}/v3/services/bank_codes").mock(
        return_value=httpx.Response(200, json=[1, 2, 3])
    )
    client = make_client()
    with pytest.raises(usesmileid.errors.UnexpectedResponseError):
        client.services.bank_codes()


def test_token_non_object_body_raises_unexpected_response(respx_mock: Any) -> None:
    respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, text="not json")
    )
    client = make_client()
    with pytest.raises(usesmileid.errors.UnexpectedResponseError):
        client.services.id_status(country="NG", id_type="NIN")


def test_token_missing_field_raises_unexpected_response(respx_mock: Any) -> None:
    respx_mock.post(f"{BASE_URL}/v3/token").mock(
        return_value=httpx.Response(200, json={"nope": True})
    )
    client = make_client()
    with pytest.raises(usesmileid.errors.UnexpectedResponseError):
        client.services.id_status(country="NG", id_type="NIN")


def test_retrieve_not_found_path_unaffected(respx_mock: Any, mock_token: Any) -> None:
    respx_mock.get(f"{BASE_URL}/v3/status/job_missing").mock(
        return_value=httpx.Response(
            404, json={"status": "not_found", "message": "Verification not found"}
        )
    )
    client = make_client()
    assert client.verifications.retrieve("job_missing").is_not_found


# -- path-segment encoding ---------------------------------------------------


def test_job_id_is_path_encoded(respx_mock: Any, mock_token: Any) -> None:
    encoded = "job%20x%2F..%2Fy%3Fq"
    route = respx_mock.get(f"{BASE_URL}/v3/status/{encoded}").mock(
        return_value=httpx.Response(200, json={"status": "complete"})
    )
    client = make_client()
    client.verifications.retrieve("job x/../y?q")
    assert route.called
    assert route.calls.last.request.url.raw_path.decode().startswith(
        f"/v3/status/{encoded}"
    )


def test_user_id_is_path_encoded_for_report_fraud(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/users/a%2Fb/report_fraud").mock(
        return_value=httpx.Response(202, json={"status": "accepted"})
    )
    client = make_client()
    client.users.flag_fraud("a/b", reason="OTHER", notes="n", reported_by="r@e.com")
    assert route.called


def test_golden_ids_stay_byte_identical(respx_mock: Any, mock_token: Any) -> None:
    job_id = "job_01h8x9y2z3a4b5c6d7e8f9g0h1"
    route = respx_mock.get(f"{BASE_URL}/v3/status/{job_id}").mock(
        return_value=httpx.Response(200, json={"status": "complete"})
    )
    client = make_client()
    client.verifications.retrieve(job_id)
    assert route.calls.last.request.url.raw_path.decode() == f"/v3/status/{job_id}"


def test_replay_job_id_is_path_encoded(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/replay/job%2Fx").mock(
        return_value=httpx.Response(202, json={"status": "accepted"})
    )
    client = make_client()
    client.verifications.replay("job/x")
    assert route.called


# -- multipart header-injection safety ----------------------------------------


class _NamedBytes(io.BytesIO):
    """A file-like object with a settable ``name`` attribute."""


def test_hostile_filename_is_sanitized_on_the_wire(
    respx_mock: Any, mock_token: Any
) -> None:
    route = respx_mock.post(f"{BASE_URL}/v3/document_verification").mock(
        return_value=httpx.Response(
            202, json={**ACCEPTED, "status": "accepted"}
        )
    )
    hostile = _NamedBytes(JPEG_BYTES)
    hostile.name = 'evil"; dummy=x\r\nX-Injected: 1\r\n.jpg'
    client = make_client()
    client.documents.verify(
        selfie_image=hostile,
        liveness_images=LIVENESS,
        document=JPEG_BYTES,
        consent=consent_dict(),
        country="NG",
        user_details=user_details_dict(),
    )
    content = route.calls.last.request.content
    # No injected header can appear at the start of a line.
    assert b"\r\nX-Injected" not in content
    parts = parse_multipart(route.calls.last.request)
    selfie = next(p for p in parts if p["name"] == "selfie_image")
    filename = selfie["filename"]
    assert filename is not None
    for forbidden in ('"', "\r", "\n", ";", "\\"):
        assert forbidden not in filename
    assert selfie["content_type"] == "image/jpeg"


def test_sanitize_filename_rules() -> None:
    assert _sanitize_filename('a"b\r\nc;d\\e.jpg') == "a_b__c_d_e.jpg"
    assert _sanitize_filename('"\r\n') == "___"
    assert _sanitize_filename("") == "upload"
    assert _sanitize_filename("selfie.jpg") == "selfie.jpg"


def test_hostile_content_type_rejected() -> None:
    with pytest.raises(usesmileid.errors.ValidationError):
        _check_media_type("image/jpeg\r\nX-Evil: 1")
    with pytest.raises(usesmileid.errors.ValidationError):
        _check_media_type('image/"jpeg"')
    assert _check_media_type("image/jpeg") == "image/jpeg"
    assert _check_media_type("application/json") == "application/json"


# -- environment validation ---------------------------------------------------


@pytest.mark.parametrize("environment", ["staging", "prod", "", "SANDBOX"])
def test_invalid_environment_rejected(environment: str) -> None:
    with pytest.raises(usesmileid.errors.ValidationError):
        make_client(environment=environment)


@pytest.mark.parametrize(
    ("environment", "base_url"),
    [
        ("sandbox", "https://testapi.smileidentity.com"),
        ("production", "https://api.smileidentity.com"),
    ],
)
def test_valid_environments_accepted(environment: str, base_url: str) -> None:
    assert make_client(environment=environment).config.base_url == base_url
