"""Thin per-operation request builders.

Each function maps typed parameters to a wire :class:`Request` — assigning every
field to its destination (path / query / header / body scalar / body JSON part /
multipart binary). The hand-written transport executes the request.

Binary inputs reach these builders already normalized to ``(filename, bytes,
content_type)`` tuples by ``smileid.helpers.multipart``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# A normalized binary part: (filename, raw bytes, content type).
BinaryPart = Tuple[str, bytes, str]


@dataclass
class Request:
    """Language-neutral description of one HTTP request."""

    method: str
    path: str
    authenticated: bool
    idempotent: bool
    needs_partner_id_header: bool = False
    user_id_header: Optional[str] = None
    query: Dict[str, str] = field(default_factory=dict)
    extra_headers: Dict[str, str] = field(default_factory=dict)
    text_parts: List[Tuple[str, str]] = field(default_factory=list)
    json_parts: List[Tuple[str, str]] = field(default_factory=list)
    binary_parts: List[Tuple[str, str, bytes, str]] = field(default_factory=list)
    json_body: Optional[dict] = None
    body_kind: str = "none"  # "multipart" | "json" | "none"
    ok_statuses: Tuple[int, ...] = (200, 202)


def _add_scalar(req: Request, name: str, value: object) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        text = "true" if value else "false"
    else:
        text = str(value)
    req.text_parts.append((name, text))


def _add_json(req: Request, name: str, value: object) -> None:
    if value is None:
        return
    req.json_parts.append((name, json.dumps(value, separators=(",", ":"))))


def _add_binary(req: Request, name: str, part: Optional[BinaryPart]) -> None:
    if part is None:
        return
    filename, data, content_type = part
    req.binary_parts.append((name, filename, data, content_type))


def _add_binary_array(req: Request, name: str, parts: Optional[List[BinaryPart]]) -> None:
    for filename, data, content_type in parts or []:
        req.binary_parts.append((name, filename, data, content_type))


def token(partner_id: str, api_key: str) -> Request:
    """POST /v3/token — internal. Lowercase headers, no body."""
    return Request(
        method="POST",
        path="/v3/token",
        authenticated=False,
        idempotent=True,
        extra_headers={"smileid-partner-id": partner_id, "smileid-api-key": api_key},
        body_kind="none",
        ok_statuses=(200,),
    )


def enhanced_kyc(
    *,
    country: str,
    id_type: str,
    id_number: str,
    user_details: dict,
    consent: dict,
    callback_url: Optional[str] = None,
    bank_code: Optional[str] = None,
    operator: Optional[str] = None,
    partner_params: Optional[dict] = None,
    metadata: Optional[list] = None,
    user_id: Optional[str] = None,
) -> Request:
    """POST /v3/enhanced_kyc. No Partner-ID header; user_id in header."""
    req = Request(
        method="POST",
        path="/v3/enhanced_kyc",
        authenticated=True,
        idempotent=False,
        user_id_header=user_id,
        body_kind="multipart",
    )
    _add_scalar(req, "country", country)
    _add_scalar(req, "id_type", id_type)
    _add_scalar(req, "id_number", id_number)
    _add_scalar(req, "callback_url", callback_url)
    _add_scalar(req, "bank_code", bank_code)
    _add_scalar(req, "operator", operator)
    _add_json(req, "user_details", user_details)
    _add_json(req, "consent", consent)
    _add_json(req, "partner_params", partner_params)
    _add_json(req, "metadata", metadata)
    return req


def document_verification(
    *,
    selfie_image: BinaryPart,
    liveness_images: List[BinaryPart],
    document: BinaryPart,
    consent: dict,
    country: str,
    user_details: dict,
    document_back: Optional[BinaryPart] = None,
    id_type: Optional[str] = None,
    callback_url: Optional[str] = None,
    partner_params: Optional[dict] = None,
    metadata: Optional[list] = None,
    user_id: Optional[str] = None,
) -> Request:
    """POST /v3/document_verification. Partner-ID header required."""
    req = Request(
        method="POST",
        path="/v3/document_verification",
        authenticated=True,
        idempotent=False,
        needs_partner_id_header=True,
        user_id_header=user_id,
        body_kind="multipart",
    )
    _add_scalar(req, "country", country)
    _add_scalar(req, "id_type", id_type)
    _add_scalar(req, "callback_url", callback_url)
    _add_binary(req, "selfie_image", selfie_image)
    _add_binary_array(req, "liveness_images", liveness_images)
    _add_binary(req, "document", document)
    _add_binary(req, "document_back", document_back)
    _add_json(req, "user_details", user_details)
    _add_json(req, "consent", consent)
    _add_json(req, "partner_params", partner_params)
    _add_json(req, "metadata", metadata)
    return req


def enhanced_document_verification(
    *,
    selfie_image: BinaryPart,
    liveness_images: List[BinaryPart],
    document: BinaryPart,
    consent: dict,
    country: str,
    id_type: str,
    user_details: dict,
    document_back: Optional[BinaryPart] = None,
    callback_url: Optional[str] = None,
    partner_params: Optional[dict] = None,
    metadata: Optional[list] = None,
    user_id: Optional[str] = None,
) -> Request:
    """POST /v3/enhanced_document_verification. id_type required."""
    req = document_verification(
        selfie_image=selfie_image,
        liveness_images=liveness_images,
        document=document,
        consent=consent,
        country=country,
        user_details=user_details,
        document_back=document_back,
        id_type=id_type,
        callback_url=callback_url,
        partner_params=partner_params,
        metadata=metadata,
        user_id=user_id,
    )
    req.path = "/v3/enhanced_document_verification"
    return req


def biometric_kyc(
    *,
    selfie_image: BinaryPart,
    liveness_images: List[BinaryPart],
    consent: dict,
    country: str,
    id_type: str,
    id_number: str,
    user_details: dict,
    callback_url: Optional[str] = None,
    sandbox_result: Optional[float] = None,
    partner_params: Optional[dict] = None,
    metadata: Optional[list] = None,
    user_id: Optional[str] = None,
) -> Request:
    """POST /v3/biometric_kyc. Partner-ID header required."""
    req = Request(
        method="POST",
        path="/v3/biometric_kyc",
        authenticated=True,
        idempotent=False,
        needs_partner_id_header=True,
        user_id_header=user_id,
        body_kind="multipart",
    )
    _add_scalar(req, "country", country)
    _add_scalar(req, "id_type", id_type)
    _add_scalar(req, "id_number", id_number)
    _add_scalar(req, "callback_url", callback_url)
    _add_scalar(req, "sandbox_result", sandbox_result)
    _add_binary(req, "selfie_image", selfie_image)
    _add_binary_array(req, "liveness_images", liveness_images)
    _add_json(req, "user_details", user_details)
    _add_json(req, "consent", consent)
    _add_json(req, "partner_params", partner_params)
    _add_json(req, "metadata", metadata)
    return req


def registration(
    *,
    selfie_image: BinaryPart,
    liveness_images: List[BinaryPart],
    consent: dict,
    user_details: dict,
    allow_new_enroll: Optional[bool] = None,
    callback_url: Optional[str] = None,
    sandbox_result: Optional[float] = None,
    partner_params: Optional[dict] = None,
    metadata: Optional[list] = None,
    user_id: Optional[str] = None,
) -> Request:
    """POST /v3/registration. No Partner-ID header; user_id in header."""
    req = Request(
        method="POST",
        path="/v3/registration",
        authenticated=True,
        idempotent=False,
        user_id_header=user_id,
        body_kind="multipart",
    )
    _add_scalar(req, "allow_new_enroll", allow_new_enroll)
    _add_scalar(req, "callback_url", callback_url)
    _add_scalar(req, "sandbox_result", sandbox_result)
    _add_binary(req, "selfie_image", selfie_image)
    _add_binary_array(req, "liveness_images", liveness_images)
    _add_json(req, "user_details", user_details)
    _add_json(req, "consent", consent)
    _add_json(req, "partner_params", partner_params)
    _add_json(req, "metadata", metadata)
    return req


def authentication(
    *,
    user_id: str,
    consent: dict,
    user_details: dict,
    selfie_image: Optional[BinaryPart] = None,
    liveness_images: Optional[List[BinaryPart]] = None,
    use_enrolled_image: Optional[bool] = None,
    callback_url: Optional[str] = None,
    sandbox_result: Optional[float] = None,
    partner_params: Optional[dict] = None,
    metadata: Optional[list] = None,
) -> Request:
    """POST /v3/authentication. user_id in BODY (required)."""
    req = Request(
        method="POST",
        path="/v3/authentication",
        authenticated=True,
        idempotent=False,
        body_kind="multipart",
    )
    _add_scalar(req, "user_id", user_id)
    _add_scalar(req, "use_enrolled_image", use_enrolled_image)
    _add_scalar(req, "callback_url", callback_url)
    _add_scalar(req, "sandbox_result", sandbox_result)
    _add_binary(req, "selfie_image", selfie_image)
    _add_binary_array(req, "liveness_images", liveness_images)
    _add_json(req, "user_details", user_details)
    _add_json(req, "consent", consent)
    _add_json(req, "partner_params", partner_params)
    _add_json(req, "metadata", metadata)
    return req


def compare(
    *,
    selfie_image: BinaryPart,
    comparison_image: BinaryPart,
    comparison_image_type: str,
    consent: dict,
    user_details: dict,
    liveness_images: Optional[List[BinaryPart]] = None,
    allow_new_enroll: Optional[bool] = None,
    user_id: Optional[str] = None,
    callback_url: Optional[str] = None,
    sandbox_result: Optional[float] = None,
    partner_params: Optional[dict] = None,
    metadata: Optional[list] = None,
) -> Request:
    """POST /v3/compare. user_id optional in BODY."""
    req = Request(
        method="POST",
        path="/v3/compare",
        authenticated=True,
        idempotent=False,
        body_kind="multipart",
    )
    _add_scalar(req, "comparison_image_type", comparison_image_type)
    _add_scalar(req, "allow_new_enroll", allow_new_enroll)
    _add_scalar(req, "user_id", user_id)
    _add_scalar(req, "callback_url", callback_url)
    _add_scalar(req, "sandbox_result", sandbox_result)
    _add_binary(req, "selfie_image", selfie_image)
    _add_binary(req, "comparison_image", comparison_image)
    _add_binary_array(req, "liveness_images", liveness_images)
    _add_json(req, "user_details", user_details)
    _add_json(req, "consent", consent)
    _add_json(req, "partner_params", partner_params)
    _add_json(req, "metadata", metadata)
    return req


def get_status(job_id: str) -> Request:
    """GET /v3/status/{jobId}. 404 returns a JobStatus body."""
    return Request(
        method="GET",
        path=f"/v3/status/{job_id}",
        authenticated=True,
        idempotent=True,
        ok_statuses=(200, 202, 404),
    )


def replay(job_id: str, callback_url: Optional[str] = None) -> Request:
    """POST /v3/replay/{job_id}. JSON body, NOT multipart."""
    return Request(
        method="POST",
        path=f"/v3/replay/{job_id}",
        authenticated=True,
        idempotent=False,
        json_body={"callback_url": callback_url} if callback_url else None,
        body_kind="json",
    )


def report_fraud(
    user_id: str,
    *,
    is_fraud: bool,
    reported_by: str,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
) -> Request:
    """POST /v3/users/{user_id}/report_fraud. Multipart."""
    req = Request(
        method="POST",
        path=f"/v3/users/{user_id}/report_fraud",
        authenticated=True,
        idempotent=False,
        body_kind="multipart",
    )
    _add_scalar(req, "is_fraud", is_fraud)
    _add_scalar(req, "reported_by", reported_by)
    _add_scalar(req, "reason", reason)
    _add_scalar(req, "notes", notes)
    return req


def bank_codes(country: Optional[str] = None) -> Request:
    """GET /v3/services/bank_codes. No auth."""
    query = {"country": country} if country else {}
    return Request(
        method="GET",
        path="/v3/services/bank_codes",
        authenticated=False,
        idempotent=True,
        query=query,
    )


def supported_id_types(country: Optional[str] = None) -> Request:
    """GET /v3/services/supported_id_types. No auth."""
    query = {"country": country} if country else {}
    return Request(
        method="GET",
        path="/v3/services/supported_id_types",
        authenticated=False,
        idempotent=True,
        query=query,
    )


def supported_documents(
    continent: Optional[str] = None,
    country_code: Optional[str] = None,
    locale: Optional[str] = None,
) -> Request:
    """GET /v3/services/supported_documents. No auth."""
    query: Dict[str, str] = {}
    if continent:
        query["continent"] = continent
    if country_code:
        query["country_code"] = country_code
    if locale:
        query["locale"] = locale
    return Request(
        method="GET",
        path="/v3/services/supported_documents",
        authenticated=False,
        idempotent=True,
        query=query,
    )


def id_status(country: str, id_type: str) -> Request:
    """GET /v3/services/id_status. Token required."""
    return Request(
        method="GET",
        path="/v3/services/id_status",
        authenticated=True,
        idempotent=True,
        query={"country": country, "id_type": id_type},
    )
