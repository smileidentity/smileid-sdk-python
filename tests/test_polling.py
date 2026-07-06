"""Matrix item 7: wait_until_complete poll helper."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

import usesmileid
from tests.conftest import BASE_URL, make_client

JOB_ID = "job_01h8x9y2z3a4b5c6d7e8f9g0h1"
PROCESSING = {
    "status": "processing",
    "job_id": JOB_ID,
    "user_id": "user_x",
    "message": "Verification is still processing",
}
COMPLETE = {
    "status": "complete",
    "job_id": JOB_ID,
    "user_id": "user_x",
    "message": "Verification completed with state: clear",
}
NOT_FOUND = {
    "status": "not_found",
    "job_id": JOB_ID,
    "user_id": "unknown",
    "message": "Verification not found",
}


@pytest.fixture(autouse=True)
def _fast_poll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("usesmileid.helpers.polling.time.sleep", lambda *_a: None)


def test_polls_until_complete(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.get(f"{BASE_URL}/v3/status/{JOB_ID}").mock(
        side_effect=[
            httpx.Response(202, json=PROCESSING),
            httpx.Response(202, json=PROCESSING),
            httpx.Response(200, json=COMPLETE),
        ]
    )
    client = make_client()
    result = client.verifications.wait_until_complete(JOB_ID, interval=0.01)
    assert result.is_complete
    assert result.message == "Verification completed with state: clear"
    assert route.call_count == 3


def test_not_found_treated_as_pending_by_default(respx_mock: Any, mock_token: Any) -> None:
    route = respx_mock.get(f"{BASE_URL}/v3/status/{JOB_ID}").mock(
        side_effect=[
            httpx.Response(404, json=NOT_FOUND),
            httpx.Response(200, json=COMPLETE),
        ]
    )
    client = make_client()
    result = client.verifications.wait_until_complete(JOB_ID, interval=0.01)
    assert result.is_complete
    assert route.call_count == 2


def test_not_found_returned_when_not_pending(respx_mock: Any, mock_token: Any) -> None:
    respx_mock.get(f"{BASE_URL}/v3/status/{JOB_ID}").mock(
        return_value=httpx.Response(404, json=NOT_FOUND)
    )
    client = make_client()
    result = client.verifications.wait_until_complete(
        JOB_ID, treat_not_found_as_pending=False
    )
    assert result.is_not_found


def test_timeout_raises_sdk_timeout_error(
    respx_mock: Any, mock_token: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx_mock.get(f"{BASE_URL}/v3/status/{JOB_ID}").mock(
        return_value=httpx.Response(202, json=PROCESSING)
    )
    # Simulate the clock jumping past the deadline after the first poll.
    clock = iter([0.0, 0.0, 100.0, 200.0, 300.0])
    monkeypatch.setattr(
        "usesmileid.helpers.polling.time.monotonic", lambda: next(clock)
    )
    client = make_client()
    with pytest.raises(usesmileid.errors.TimeoutError):
        client.verifications.wait_until_complete(JOB_ID, timeout=60.0, interval=0.01)


def test_interval_is_respected(
    respx_mock: Any, mock_token: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    sleeps = []
    monkeypatch.setattr("usesmileid.helpers.polling.time.sleep", lambda s: sleeps.append(s))
    respx_mock.get(f"{BASE_URL}/v3/status/{JOB_ID}").mock(
        side_effect=[
            httpx.Response(202, json=PROCESSING),
            httpx.Response(200, json=COMPLETE),
        ]
    )
    client = make_client()
    client.verifications.wait_until_complete(JOB_ID, interval=5.0)
    assert sleeps == [5.0]
