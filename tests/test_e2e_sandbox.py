"""Matrix item 8: end-to-end sandbox Enhanced KYC.

Requires real sandbox credentials via the SMILE_PARTNER_ID and SMILE_API_KEY
environment variables. Skips cleanly when they are not set. Credential values
are never printed or logged.

Targets the sandbox by default. Set SMILE_BASE_URL to point the run at another
environment, for example https://devapi.smileidentity.com.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

import usesmileid

_PARTNER_ID = os.environ.get("SMILE_PARTNER_ID")
_API_KEY = os.environ.get("SMILE_API_KEY")
_BASE_URL = os.environ.get("SMILE_BASE_URL") or None

pytestmark = pytest.mark.skipif(
    not (_PARTNER_ID and _API_KEY),
    reason="SMILE_PARTNER_ID and SMILE_API_KEY not set; skipping sandbox E2E",
)


def test_sandbox_enhanced_kyc_completes() -> None:
    assert _PARTNER_ID is not None and _API_KEY is not None
    with usesmileid.Client(
        partner_id=_PARTNER_ID,
        api_key=_API_KEY,
        environment="sandbox",
        # None keeps the sandbox URL; SMILE_BASE_URL overrides it.
        base_url=_BASE_URL,
    ) as client:
        accepted = client.enhanced_kyc.verify(
            country="NG",
            id_type="NIN",
            id_number="12345678901",
            # Non-production environments only accept recognized test
            # identities, matched on given_names + last_name + email.
            user_details={
                "given_names": "Amina Fatou",
                "last_name": "Clearwater",
                "email": "amina.clearwater@example.com",
            },
            consent=usesmileid.Consent.granted(
                granted_at=datetime.now(timezone.utc),
                notice_language="EN",
                notice_privacy_policy_url="https://example.com/privacy",
            ),
        )
        assert accepted.is_accepted
        assert accepted.job_id

        status = client.verifications.wait_until_complete(
            accepted.job_id, interval=2.0, timeout=120.0
        )
        assert status.is_complete
        # Clearwater is the "clear" test identity.
        assert status.status == "clear"
