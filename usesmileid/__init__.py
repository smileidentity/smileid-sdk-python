"""Official Smile ID server-side SDK for Python — V3 APIs.

Typical use::

    import usesmileid
    from datetime import datetime, timezone

    smile = usesmileid.Client(
        partner_id="1234",
        api_key="...",
        environment="sandbox",
    )
    accepted = smile.enhanced_kyc.verify(
        country="NG",
        id_type="NIN",
        id_number="12345678901",
        user_details={"given_names": "John", "last_name": "Doe", "email": "john@example.com"},
        consent=usesmileid.Consent.granted(
            granted_at=datetime.now(timezone.utc),
            notice_language="EN",
            notice_privacy_policy_url="https://example.com/privacy",
        ),
    )
    accepted.is_accepted  # True
"""

from usesmileid import errors
from usesmileid._version import __version__
from usesmileid.client import Client, ClientConfig
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
from usesmileid.helpers import Consent, UserDetails

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
