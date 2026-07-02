"""Official Smile ID server-side SDK for Python — V3 APIs.

Typical use::

    import smileid
    from datetime import datetime, timezone

    smile = smileid.Client(
        partner_id="1234",
        api_key="...",
        environment="sandbox",
    )
    accepted = smile.enhanced_kyc.verify(
        country="NG",
        id_type="NIN",
        id_number="12345678901",
        user_details={"given_names": "John", "last_name": "Doe", "email": "john@example.com"},
        consent=smileid.Consent.granted(
            granted_at=datetime.now(timezone.utc),
            notice_language="EN",
            notice_privacy_policy_url="https://example.com/privacy",
        ),
    )
    accepted.is_accepted  # True
"""

from smileid import errors
from smileid._version import __version__
from smileid.client import Client, ClientConfig
from smileid.generated.models import (
    AcceptedResponse,
    BankCodesResponse,
    IdStatusResponse,
    JobStatus,
    ReplayCallbackResponse,
    ReportUserFraudResponse,
    SupportedDocumentsResponse,
    SupportedIdTypesResponse,
)
from smileid.helpers import Consent, UserDetails

__all__ = [
    "__version__",
    "Client",
    "ClientConfig",
    "Consent",
    "UserDetails",
    "errors",
    "AcceptedResponse",
    "JobStatus",
    "ReplayCallbackResponse",
    "ReportUserFraudResponse",
    "BankCodesResponse",
    "SupportedIdTypesResponse",
    "SupportedDocumentsResponse",
    "IdStatusResponse",
]
