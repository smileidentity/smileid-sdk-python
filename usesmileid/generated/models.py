"""Wire response models. Field names are verbatim snake_case.

All models ignore unknown fields so that additive backend changes never break
deserialization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class _WireModel(BaseModel):
    """Base for every wire model: tolerate unknown fields, allow field names."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class AcceptedResponse(_WireModel):
    """Entry-endpoint 202 response.

    ``status`` differs by endpoint (``Accepted`` vs ``accepted``); use
    :pyattr:`is_accepted` rather than comparing the raw string.
    """

    status: str
    message: Optional[str] = None
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    created_at: Optional[str] = None

    @property
    def is_accepted(self) -> bool:
        """Normalized acceptance flag: ``status.lower() == "accepted"``."""
        return self.status.lower() == "accepted"


class JobStatus(_WireModel):
    """GET /v3/status response.

    ``status`` is ``processing`` while the job runs and ``not_found`` for a job
    the API does not know about. Any other value is the terminal decision, and
    the decision is the status itself: ``clear``, ``block``, ``attention`` or
    ``error``. ``message`` carries no sub-state — it reads "Job completed" on
    every finished job.
    """

    status: str
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    message: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        """True once the job is terminal: neither ``processing`` nor ``not_found``.

        An empty status is never terminal — a truncated response must not stop
        a poller with no decision to report.
        """
        return bool(self.status) and self.status not in ("processing", "not_found")

    @property
    def is_processing(self) -> bool:
        return self.status == "processing"

    @property
    def is_not_found(self) -> bool:
        return self.status == "not_found"


class ReplayCallbackResponse(_WireModel):
    """POST /v3/replay/{job_id} response."""

    status: str
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    message: Optional[str] = None


class ReportUserFraudResponse(_WireModel):
    """POST /v3/users/{user_id}/report_fraud response."""

    status: str
    message: Optional[str] = None
    user_id: Optional[str] = None


class BankCode(_WireModel):
    code: str
    country: str
    name: str


class BankCodesResponse(_WireModel):
    bank_codes: List[BankCode]


class SupportedIdType(_WireModel):
    country: str
    label: str
    regex: str
    type: str
    required_fields: List[str] = []
    bank_code: Optional[str] = None


class SupportedIdTypesResponse(_WireModel):
    id_types: List[SupportedIdType]


class DocumentCountry(_WireModel):
    code: str
    name: str
    continent: Optional[str] = None


class DocumentIdType(_WireModel):
    code: str
    name: str
    example: List[str] = []
    has_back: Optional[bool] = None


class SupportedDocument(_WireModel):
    country: DocumentCountry
    id_types: List[DocumentIdType] = []


class SupportedDocumentsResponse(_WireModel):
    valid_documents: List[SupportedDocument]


class IdStatusResponse(_WireModel):
    last_checked: Optional[str] = None
    last_check_status: Optional[str] = None
    last_hour_success_rate: Optional[str] = None
    last_known_status: Optional[str] = None
    last_check_success_rate: Optional[str] = None


class AmlUserProvidedInfo(_WireModel):
    given_names: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None


class OneTimeAmlResult(_WireModel):
    """One-Time AML result: the 200 body of POST /v3/aml/sync and the async callback.

    ``status`` is the decision: ``clear``, ``block``, ``attention`` or ``error``.
    Each entry of ``people`` is kept as the raw match record.
    """

    status: str
    message: str
    reason: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    product: Optional[str] = None
    partner_params: Optional[Dict[str, str]] = None
    kyc_receipt: Optional[str] = None
    strict_match: Optional[bool] = None
    no_of_persons_found: Optional[int] = None
    people: List[Dict[str, Any]] = []
    user_provided_info: Optional[AmlUserProvidedInfo] = None
    consent: Optional[Dict[str, Any]] = None
    antifraud: Optional[Dict[str, Any]] = None
    device_signals: Optional[Dict[str, Any]] = None


class AmlMonitoringNewsItem(_WireModel):
    body: str
    published_date: str
    publisher: str
    publisher_country_code: str
    title: str
    url: str


class AmlMonitoringNewsMeta(_WireModel):
    current_page: int
    limit: int
    total_count: int


class AmlMonitoringNewsResponse(_WireModel):
    """GET /v3/aml/monitoring/{job_id}/news/{reference} response."""

    job_id: str
    product: str
    user_id: str
    meta: AmlMonitoringNewsMeta
    news: List[AmlMonitoringNewsItem] = []
