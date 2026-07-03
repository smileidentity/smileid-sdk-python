# smileid

![PyPI version](https://img.shields.io/badge/pypi-unpublished-lightgrey)
![CI status](https://img.shields.io/badge/ci-pending-lightgrey)
![License](https://img.shields.io/badge/license-MIT-blue)

Official Smile ID server-side SDK for Python — V3 APIs.

This project is under active development. It is not yet published to PyPI, and the API is not stable. Do not use it in production yet.

The package and the importable module are both named `smileid`. Python 3.8 or later is required.

## Install

```bash
pip install smileid
```

## Getting started

Construct one client with your partner ID and API key. The SDK manages authentication for you: it fetches a short-lived token from the Smile ID API, caches it until it expires, and refreshes it automatically. You never handle tokens yourself.

```python
import os

import smileid

smile = smileid.Client(
    partner_id="1234",
    api_key=os.environ["SMILE_API_KEY"],
    environment="sandbox",  # the default
)
```

### Environment selection

The client targets the sandbox by default. Set `environment="production"` to go live:

- `sandbox` → `https://testapi.smileidentity.com`
- `production` → `https://api.smileidentity.com`

You can pass `base_url` to override the URL entirely (it wins over `environment`). The value must be an absolute `https` URL with no query or fragment — anything else raises `smileid.errors.ValidationError` at construction. There is deliberately no way to turn this off: partner credentials and personal data travel on every request. `environment` must be `"sandbox"` or `"production"`; any other value is rejected at construction.

### Callback URLs

Callback URLs must also be `https`. The SDK validates `default_callback_url` when you construct the client, and any per-request `callback_url` before it sends the request.

### Other options

| Option | Default | Purpose |
|---|---|---|
| `default_callback_url` | unset | Used when a call omits `callback_url`; must be https |
| `timeout` | 30 seconds | Per-request total timeout; each method also accepts a `timeout` override |
| `max_retries` | 2 | Retries for idempotent operations only (see Retries below) |
| `http_client` | SDK default | Inject your own `httpx.Client` for testing or proxies |

### Binary inputs

Every image parameter (`selfie_image`, `liveness_images`, `document`, `document_back`, `comparison_image`) accepts a file path (`str` or `os.PathLike`), raw `bytes`, or an open file object.

### Consent and user details

All verification submissions need a consent record and the user's details. Build consent with the helper; pass user details as a dict or a `smileid.UserDetails`. At least one of `email` or `phone_number` is required — the SDK checks this before sending.

```python
from datetime import datetime, timezone

consent = smileid.Consent.granted(
    granted_at=datetime.now(timezone.utc),
    notice_language="EN",
    notice_privacy_policy_url="https://example.com/privacy",
)
user_details = {"given_names": "John", "last_name": "Doe", "email": "john@example.com"}
```

The examples below assume `smile`, `consent` and `user_details` are defined as above.

## Methods

### Enhanced KYC

Verify an ID number against the issuing authority.

```python
accepted = smile.enhanced_kyc.verify(
    country="NG",
    id_type="NIN",
    id_number="12345678901",
    user_details=user_details,
    consent=consent,
)
print(accepted.job_id, accepted.is_accepted)
```

### Document verification

Verify a selfie against a photo of an identity document. `id_type` is optional; the document type is auto-classified when omitted.

```python
accepted = smile.documents.verify(
    selfie_image="selfie.jpg",
    liveness_images=["live1.jpg", "live2.jpg", "live3.jpg",
                     "live4.jpg", "live5.jpg", "live6.jpg"],
    document="passport_front.jpg",
    country="NG",
    user_details=user_details,
    consent=consent,
)
```

### Enhanced document verification

Same as document verification, but `id_type` is required and the ID information is also checked against the issuing authority.

```python
accepted = smile.documents.verify_enhanced(
    selfie_image="selfie.jpg",
    liveness_images=["live1.jpg", "live2.jpg", "live3.jpg",
                     "live4.jpg", "live5.jpg", "live6.jpg"],
    document="license_front.jpg",
    document_back="license_back.jpg",
    country="NG",
    id_type="DRIVERS_LICENSE",
    user_details=user_details,
    consent=consent,
)
```

### Biometric KYC

Verify a selfie against the photo on file with an ID authority.

```python
accepted = smile.biometric_kyc.verify(
    selfie_image="selfie.jpg",
    liveness_images=["live1.jpg", "live2.jpg", "live3.jpg",
                     "live4.jpg", "live5.jpg", "live6.jpg"],
    country="NG",
    id_type="NIN",
    id_number="12345678901",
    user_details=user_details,
    consent=consent,
)
```

### Biometric enrollment

Register a user's selfie for later authentication.

```python
accepted = smile.biometric.enroll(
    selfie_image="selfie.jpg",
    liveness_images=["live1.jpg", "live2.jpg", "live3.jpg",
                     "live4.jpg", "live5.jpg", "live6.jpg"],
    user_details=user_details,
    consent=consent,
    user_id="user_01h8x9y2z3a4b5c6d7e8f9g0h1",
)
```

### Biometric authentication

Authenticate a previously enrolled user. Set `use_enrolled_image=True` to re-use the enrolled image instead of uploading a new selfie.

```python
accepted = smile.biometric.authenticate(
    user_id="user_01h8x9y2z3a4b5c6d7e8f9g0h1",
    selfie_image="selfie.jpg",
    liveness_images=["live1.jpg", "live2.jpg", "live3.jpg",
                     "live4.jpg", "live5.jpg", "live6.jpg"],
    user_details=user_details,
    consent=consent,
)
```

### Selfie comparison

Compare a selfie against another image (a document photo, ID photo or portrait).

```python
accepted = smile.biometric.compare(
    selfie_image="selfie.jpg",
    comparison_image="id_photo.jpg",
    comparison_image_type="ID_PHOTO",  # DOCUMENT | ID_PHOTO | PORTRAIT
    user_details=user_details,
    consent=consent,
)
```

### Check a verification's status

```python
status = smile.verifications.retrieve("job_01h8x9y2z3a4b5c6d7e8f9g0h1")
print(status.status)  # "complete", "processing" or "not_found"
```

A job that is not found returns a `JobStatus` with `status="not_found"` — it does not raise an error, so polling can distinguish "not found yet" cleanly.

### Wait for a verification to complete

Polls the status endpoint until the job completes. Raises `smileid.errors.TimeoutError` if it does not complete in time.

```python
status = smile.verifications.wait_until_complete(
    "job_01h8x9y2z3a4b5c6d7e8f9g0h1",
    interval=2.0,   # seconds between polls
    timeout=60.0,   # give up after this many seconds
)
print(status.message)
```

By default a `not_found` status is treated as "not found yet" and polling continues; pass `treat_not_found_as_pending=False` to return it immediately.

### Replay a callback

Re-send the callback for a completed verification.

```python
replayed = smile.verifications.replay(
    "job_01h8x9y2z3a4b5c6d7e8f9g0h1",
    callback_url="https://app.example.com/webhook",  # optional override
)
```

Replaying a job that is still processing raises `smileid.errors.ConflictError`.

### Report user fraud

Flag a user as fraudulent, or clear a previous flag. `flag_fraud` and `clear_fraud` are convenience wrappers over `report_fraud`.

```python
smile.users.flag_fraud(
    "user_01h8x9y2z3a4b5c6d7e8f9g0h1",
    reason="FIRST_PARTY_FRAUD",
    reported_by="risk@example.com",
)

smile.users.clear_fraud(
    "user_01h8x9y2z3a4b5c6d7e8f9g0h1",
    notes="Cleared after review",
    reported_by="risk@example.com",
)
```

`reason` is required when flagging; `notes` is required when clearing or when `reason="OTHER"`. The SDK checks these rules before sending.

### List bank codes

No authentication required.

```python
banks = smile.services.bank_codes(country="NG")
for bank in banks.bank_codes:
    print(bank.code, bank.name)
```

### List supported ID types

No authentication required.

```python
id_types = smile.services.supported_id_types(country="NG")
for id_type in id_types.id_types:
    print(id_type.type, id_type.label)
```

### List supported documents

No authentication required.

```python
documents = smile.services.supported_documents(country_code="NG")
for entry in documents.valid_documents:
    print(entry.country.name, [d.code for d in entry.id_types])
```

### Check ID type availability

```python
status = smile.services.id_status(country="NG", id_type="NIN")
print(status.last_known_status, status.last_hour_success_rate)
```

## Responses

Submission endpoints return an `AcceptedResponse`. Use `response.is_accepted` rather than comparing the raw `status` string — the API returns both `"Accepted"` and `"accepted"` depending on the endpoint, and `is_accepted` normalizes the difference.

## Error handling

All errors raised by the SDK subclass `smileid.errors.SmileIDError` and expose `status_code`, `status`, `message`, `code`, `request_id` and `raw_body`.

```python
import smileid.errors

try:
    accepted = smile.enhanced_kyc.verify(...)
except smileid.errors.PaymentRequiredError:
    ...  # top up your wallet
except smileid.errors.InvalidRequestError as err:
    print(err.status_code, err.message)
except smileid.errors.SmileIDError as err:
    ...  # everything else
```

| Error | Raised on |
|---|---|
| `InvalidRequestError` | HTTP 400, 415 |
| `ValidationError` | Client-side validation, before any request is sent |
| `AuthenticationError` | HTTP 401 (after one automatic token refresh) |
| `PaymentRequiredError` | HTTP 402 |
| `PermissionError` | HTTP 403 |
| `NotFoundError` | HTTP 404 |
| `ConflictError` | HTTP 409 |
| `PayloadTooLargeError` | HTTP 413 |
| `RateLimitError` | HTTP 429 |
| `APIError` | HTTP 5xx |
| `UnexpectedResponseError` | A success response whose body is not a JSON object |
| `ConnectionError` | Network failure or timeout, no HTTP response |
| `TimeoutError` | `wait_until_complete` deadline reached |

## Retries

The SDK automatically retries idempotent operations only: status and services reads, and the internal token fetch. Retries cover connection errors and HTTP 408, 429 and 5xx, with exponential backoff, and honour the `Retry-After` header. HTTP 409 is never retried.

Submission calls (verification, enrollment, authentication, compare, replay, fraud reports) are never retried automatically, because a retry could create a duplicate job. A connection failure on these raises `smileid.errors.ConnectionError` and you decide whether to retry.

## Telemetry

Every request carries three telemetry headers: `SmileID-Source-SDK`, `SmileID-Source-SDK-Version` and `User-Agent`. They identify the SDK and its version for observability. They are never used for authentication and carry no personal data.

## Licence

This project is licensed under the MIT licence. See [LICENSE](LICENSE) for details.

## Security

See [SECURITY.md](SECURITY.md) for how to report a vulnerability.
