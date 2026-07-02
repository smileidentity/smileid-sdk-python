"""Wire response models. Field names are verbatim snake_case.

All models ignore unknown fields so that additive backend changes never break
deserialization.
"""

from __future__ import annotations

from typing import List, Optional

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

    ``status`` is one of ``complete``, ``processing`` or ``not_found``.
    """

    status: str
    job_id: Optional[str] = None
    user_id: Optional[str] = None
    message: Optional[str] = None

    @property
    def is_complete(self) -> bool:
        return self.status == "complete"

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
