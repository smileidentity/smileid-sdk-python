"""Direct tests for the generator-owned layer in ``usesmileid.generated``.

CI requires 100% line and branch coverage of this package, so every builder
branch and model property is exercised here, independent of the client.
"""

from __future__ import annotations

import pytest

from usesmileid.generated import operations
from usesmileid.generated.models import JobStatus


@pytest.mark.parametrize(
    ("status", "processing", "not_found", "complete"),
    [
        ("processing", True, False, False),
        ("not_found", False, True, False),
        ("clear", False, False, True),
        ("", False, False, False),
    ],
)
def test_job_status_flags(status: str, processing: bool, not_found: bool, complete: bool) -> None:
    job = JobStatus(status=status)
    assert job.is_processing is processing
    assert job.is_not_found is not_found
    assert job.is_complete is complete


def test_supported_documents_sends_no_query_when_no_filters() -> None:
    request = operations.supported_documents()
    assert request.method == "GET"
    assert request.path == "/v3/services/supported_documents"
    assert request.authenticated is False
    assert request.query == {}


def test_supported_documents_sends_every_filter() -> None:
    request = operations.supported_documents(continent="Africa", country_code="NG", locale="en")
    assert request.query == {"continent": "Africa", "country_code": "NG", "locale": "en"}


def test_supported_documents_sends_only_set_filters() -> None:
    request = operations.supported_documents(continent="Africa")
    assert request.query == {"continent": "Africa"}
