"""The Smile ID client and its resource namespaces.

Canonical surface: ``client.<resource>.<verb>(...)``. Wire fields stay
snake_case; per-request overrides (``callback_url``, ``timeout``) are keyword
arguments.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, List, Optional, Type, Union

import httpx

from usesmileid.client.config import ClientConfig, validate_callback_url
from usesmileid.client.transport import Transport
from usesmileid.errors import ValidationError, parse_success_json
from usesmileid.generated import operations
from usesmileid.generated.models import (
    AcceptedResponse,
    BankCodesResponse,
    IdStatusResponse,
    JobStatus,
    ReplayCallbackResponse,
    ReportUserFraudResponse,
    SupportedDocumentsResponse,
    SupportedIdTypesResponse,
)
from usesmileid.helpers.consent import Consent
from usesmileid.helpers.fraud import validate_fraud_report
from usesmileid.helpers.multipart import normalize_binary, normalize_binary_list
from usesmileid.helpers.polling import wait_until_complete
from usesmileid.helpers.user_details import UserDetails, normalize_user_details

ConsentInput = Union[Consent, dict]
UserDetailsInput = Union[UserDetails, dict]


def _consent_dict(consent: ConsentInput) -> dict:
    if isinstance(consent, dict):
        return consent
    to_dict = getattr(consent, "to_dict", None)
    if callable(to_dict):
        result = to_dict()
        if isinstance(result, dict):
            return result
    raise ValidationError("consent must be a Consent or a dict")


class _Resource:
    def __init__(self, client: "Client") -> None:
        self._client = client

    @property
    def _transport(self) -> Transport:
        return self._client._transport

    def _callback(self, callback_url: Optional[str]) -> Optional[str]:
        return self._client._resolve_callback(callback_url)


class EnhancedKycResource(_Resource):
    def verify(
        self,
        *,
        country: str,
        id_type: str,
        id_number: str,
        user_details: UserDetailsInput,
        consent: ConsentInput,
        callback_url: Optional[str] = None,
        bank_code: Optional[str] = None,
        operator: Optional[str] = None,
        partner_params: Optional[dict] = None,
        metadata: Optional[list] = None,
        user_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AcceptedResponse:
        """POST /v3/enhanced_kyc."""
        request = operations.enhanced_kyc(
            country=country,
            id_type=id_type,
            id_number=id_number,
            user_details=normalize_user_details(user_details),
            consent=_consent_dict(consent),
            callback_url=self._callback(callback_url),
            bank_code=bank_code,
            operator=operator,
            partner_params=partner_params,
            metadata=metadata,
            user_id=user_id,
        )
        response = self._transport.send(request, timeout=timeout)
        return AcceptedResponse.model_validate(parse_success_json(response))


class DocumentsResource(_Resource):
    def verify(
        self,
        *,
        selfie_image: Any,
        liveness_images: Any,
        document: Any,
        consent: ConsentInput,
        country: str,
        user_details: UserDetailsInput,
        document_back: Any = None,
        id_type: Optional[str] = None,
        callback_url: Optional[str] = None,
        partner_params: Optional[dict] = None,
        metadata: Optional[list] = None,
        user_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AcceptedResponse:
        """POST /v3/document_verification."""
        request = operations.document_verification(
            selfie_image=_selfie(selfie_image),
            liveness_images=_liveness(liveness_images),
            document=_document(document, "document.jpg"),
            document_back=_document(document_back, "document_back.jpg"),
            consent=_consent_dict(consent),
            country=country,
            id_type=id_type,
            user_details=normalize_user_details(user_details),
            callback_url=self._callback(callback_url),
            partner_params=partner_params,
            metadata=metadata,
            user_id=user_id,
        )
        response = self._transport.send(request, timeout=timeout)
        return AcceptedResponse.model_validate(parse_success_json(response))

    def verify_enhanced(
        self,
        *,
        selfie_image: Any,
        liveness_images: Any,
        document: Any,
        consent: ConsentInput,
        country: str,
        id_type: str,
        user_details: UserDetailsInput,
        document_back: Any = None,
        callback_url: Optional[str] = None,
        partner_params: Optional[dict] = None,
        metadata: Optional[list] = None,
        user_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AcceptedResponse:
        """POST /v3/enhanced_document_verification. id_type required."""
        if not id_type:
            raise ValidationError("id_type is required for verify_enhanced")
        request = operations.enhanced_document_verification(
            selfie_image=_selfie(selfie_image),
            liveness_images=_liveness(liveness_images),
            document=_document(document, "document.jpg"),
            document_back=_document(document_back, "document_back.jpg"),
            consent=_consent_dict(consent),
            country=country,
            id_type=id_type,
            user_details=normalize_user_details(user_details),
            callback_url=self._callback(callback_url),
            partner_params=partner_params,
            metadata=metadata,
            user_id=user_id,
        )
        response = self._transport.send(request, timeout=timeout)
        return AcceptedResponse.model_validate(parse_success_json(response))


class BiometricKycResource(_Resource):
    def verify(
        self,
        *,
        selfie_image: Any,
        liveness_images: Any,
        consent: ConsentInput,
        country: str,
        id_type: str,
        id_number: str,
        user_details: UserDetailsInput,
        callback_url: Optional[str] = None,
        sandbox_result: Optional[float] = None,
        partner_params: Optional[dict] = None,
        metadata: Optional[list] = None,
        user_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AcceptedResponse:
        """POST /v3/biometric_kyc."""
        request = operations.biometric_kyc(
            selfie_image=_selfie(selfie_image),
            liveness_images=_liveness(liveness_images),
            consent=_consent_dict(consent),
            country=country,
            id_type=id_type,
            id_number=id_number,
            user_details=normalize_user_details(user_details),
            callback_url=self._callback(callback_url),
            sandbox_result=sandbox_result,
            partner_params=partner_params,
            metadata=metadata,
            user_id=user_id,
        )
        response = self._transport.send(request, timeout=timeout)
        return AcceptedResponse.model_validate(parse_success_json(response))


class BiometricResource(_Resource):
    def enroll(
        self,
        *,
        selfie_image: Any,
        liveness_images: Any,
        consent: ConsentInput,
        user_details: UserDetailsInput,
        allow_new_enroll: Optional[bool] = None,
        callback_url: Optional[str] = None,
        sandbox_result: Optional[float] = None,
        partner_params: Optional[dict] = None,
        metadata: Optional[list] = None,
        user_id: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AcceptedResponse:
        """POST /v3/registration."""
        request = operations.registration(
            selfie_image=_selfie(selfie_image),
            liveness_images=_liveness(liveness_images),
            consent=_consent_dict(consent),
            user_details=normalize_user_details(user_details),
            allow_new_enroll=allow_new_enroll,
            callback_url=self._callback(callback_url),
            sandbox_result=sandbox_result,
            partner_params=partner_params,
            metadata=metadata,
            user_id=user_id,
        )
        response = self._transport.send(request, timeout=timeout)
        return AcceptedResponse.model_validate(parse_success_json(response))

    def authenticate(
        self,
        *,
        user_id: str,
        consent: ConsentInput,
        user_details: UserDetailsInput,
        selfie_image: Any = None,
        liveness_images: Any = None,
        use_enrolled_image: Optional[bool] = None,
        callback_url: Optional[str] = None,
        sandbox_result: Optional[float] = None,
        partner_params: Optional[dict] = None,
        metadata: Optional[list] = None,
        timeout: Optional[float] = None,
    ) -> AcceptedResponse:
        """POST /v3/authentication. user_id in body."""
        if not use_enrolled_image:
            if selfie_image is None or liveness_images is None:
                raise ValidationError(
                    "selfie_image and liveness_images are required "
                    "unless use_enrolled_image is true"
                )
        request = operations.authentication(
            user_id=user_id,
            consent=_consent_dict(consent),
            user_details=normalize_user_details(user_details),
            selfie_image=_selfie(selfie_image),
            liveness_images=_liveness(liveness_images),
            use_enrolled_image=use_enrolled_image,
            callback_url=self._callback(callback_url),
            sandbox_result=sandbox_result,
            partner_params=partner_params,
            metadata=metadata,
        )
        response = self._transport.send(request, timeout=timeout)
        return AcceptedResponse.model_validate(parse_success_json(response))

    def compare(
        self,
        *,
        selfie_image: Any,
        comparison_image: Any,
        comparison_image_type: str,
        consent: ConsentInput,
        user_details: UserDetailsInput,
        liveness_images: Any = None,
        allow_new_enroll: Optional[bool] = None,
        user_id: Optional[str] = None,
        callback_url: Optional[str] = None,
        sandbox_result: Optional[float] = None,
        partner_params: Optional[dict] = None,
        metadata: Optional[list] = None,
        timeout: Optional[float] = None,
    ) -> AcceptedResponse:
        """POST /v3/compare."""
        request = operations.compare(
            selfie_image=_selfie(selfie_image),
            comparison_image=_selfie(comparison_image, "comparison.jpg"),
            comparison_image_type=comparison_image_type,
            consent=_consent_dict(consent),
            user_details=normalize_user_details(user_details),
            liveness_images=_liveness(liveness_images),
            allow_new_enroll=allow_new_enroll,
            user_id=user_id,
            callback_url=self._callback(callback_url),
            sandbox_result=sandbox_result,
            partner_params=partner_params,
            metadata=metadata,
        )
        response = self._transport.send(request, timeout=timeout)
        return AcceptedResponse.model_validate(parse_success_json(response))


class VerificationsResource(_Resource):
    def retrieve(self, job_id: str, *, timeout: Optional[float] = None) -> JobStatus:
        """GET /v3/status/{jobId}. 404 returns a not_found JobStatus."""
        request = operations.get_status(job_id)
        response = self._transport.send(request, timeout=timeout)
        return JobStatus.model_validate(parse_success_json(response))

    def wait_until_complete(
        self,
        job_id: str,
        *,
        interval: float = 2.0,
        timeout: float = 60.0,
        treat_not_found_as_pending: bool = True,
    ) -> JobStatus:
        """Poll retrieve until the job reaches a terminal status.

        Polls while the status is ``processing`` or ``not_found``, and returns
        on any other status (``clear``, ``block``, ``attention`` or ``error``).
        """
        return wait_until_complete(
            self.retrieve,
            job_id,
            interval=interval,
            timeout=timeout,
            treat_not_found_as_pending=treat_not_found_as_pending,
        )

    def replay(
        self,
        job_id: str,
        *,
        callback_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> ReplayCallbackResponse:
        """POST /v3/replay/{job_id}."""
        request = operations.replay(job_id, self._callback(callback_url))
        response = self._transport.send(request, timeout=timeout)
        return ReplayCallbackResponse.model_validate(parse_success_json(response))


class UsersResource(_Resource):
    def report_fraud(
        self,
        user_id: str,
        *,
        is_fraud: bool,
        reported_by: str,
        reason: Optional[str] = None,
        notes: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> ReportUserFraudResponse:
        """POST /v3/users/{user_id}/report_fraud."""
        validate_fraud_report(is_fraud=is_fraud, reason=reason, notes=notes)
        request = operations.report_fraud(
            user_id,
            is_fraud=is_fraud,
            reported_by=reported_by,
            reason=reason,
            notes=notes,
        )
        response = self._transport.send(request, timeout=timeout)
        return ReportUserFraudResponse.model_validate(parse_success_json(response))

    def flag_fraud(
        self,
        user_id: str,
        *,
        reason: str,
        reported_by: str,
        notes: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> ReportUserFraudResponse:
        """Convenience wrapper: report_fraud with is_fraud=true."""
        return self.report_fraud(
            user_id,
            is_fraud=True,
            reported_by=reported_by,
            reason=reason,
            notes=notes,
            timeout=timeout,
        )

    def clear_fraud(
        self,
        user_id: str,
        *,
        notes: str,
        reported_by: str,
        timeout: Optional[float] = None,
    ) -> ReportUserFraudResponse:
        """Convenience wrapper: report_fraud with is_fraud=false."""
        return self.report_fraud(
            user_id,
            is_fraud=False,
            reported_by=reported_by,
            notes=notes,
            timeout=timeout,
        )


class ServicesResource(_Resource):
    def bank_codes(
        self, *, country: Optional[str] = None, timeout: Optional[float] = None
    ) -> BankCodesResponse:
        """GET /v3/services/bank_codes. No auth."""
        response = self._transport.send(operations.bank_codes(country), timeout=timeout)
        return BankCodesResponse.model_validate(parse_success_json(response))

    def supported_id_types(
        self, *, country: Optional[str] = None, timeout: Optional[float] = None
    ) -> SupportedIdTypesResponse:
        """GET /v3/services/supported_id_types. No auth."""
        response = self._transport.send(
            operations.supported_id_types(country), timeout=timeout
        )
        return SupportedIdTypesResponse.model_validate(parse_success_json(response))

    def supported_documents(
        self,
        *,
        continent: Optional[str] = None,
        country_code: Optional[str] = None,
        locale: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> SupportedDocumentsResponse:
        """GET /v3/services/supported_documents. No auth."""
        response = self._transport.send(
            operations.supported_documents(continent, country_code, locale),
            timeout=timeout,
        )
        return SupportedDocumentsResponse.model_validate(parse_success_json(response))

    def id_status(
        self, *, country: str, id_type: str, timeout: Optional[float] = None
    ) -> IdStatusResponse:
        """GET /v3/services/id_status. Token required."""
        response = self._transport.send(
            operations.id_status(country, id_type), timeout=timeout
        )
        return IdStatusResponse.model_validate(parse_success_json(response))


def _selfie(value: Any, default_filename: str = "selfie.jpg") -> Any:
    """Selfie-family inputs (selfie, comparison, liveness) are always JPEG."""
    return normalize_binary(value, default_filename=default_filename)


def _document(value: Any, default_filename: str) -> Any:
    """document / document_back are the only fields that may be PNG."""
    return normalize_binary(value, default_filename=default_filename, allow_png=True)


def _liveness(values: Any) -> Any:
    return normalize_binary_list(values, prefix="liveness")


class Client:
    """The Smile ID V3 client.

    Construct with a partner_id and api_key; everything else has a default.
    Usable as a context manager to close the underlying HTTP client.
    """

    def __init__(
        self,
        *,
        partner_id: str,
        api_key: str,
        environment: str = "sandbox",
        default_callback_url: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 2,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._config = ClientConfig(
            partner_id=partner_id,
            api_key=api_key,
            environment=environment,
            default_callback_url=default_callback_url,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        self._transport = Transport(self._config, http_client=http_client)

        self.enhanced_kyc = EnhancedKycResource(self)
        self.documents = DocumentsResource(self)
        self.biometric_kyc = BiometricKycResource(self)
        self.biometric = BiometricResource(self)
        self.verifications = VerificationsResource(self)
        self.users = UsersResource(self)
        self.services = ServicesResource(self)

    @property
    def config(self) -> ClientConfig:
        return self._config

    def _resolve_callback(self, callback_url: Optional[str]) -> Optional[str]:
        resolved = callback_url if callback_url is not None else self._config.default_callback_url
        if resolved is not None:
            validate_callback_url(resolved)
        return resolved

    def close(self) -> None:
        self._transport.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()


__all__: List[str] = ["Client"]
