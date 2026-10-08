# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [12.2.0] - 2026-10-08

### Changed

- Each request mints its own token, bound to that request's `user_id` and product, instead of reusing one cached token. A 401 is no longer retried with a refreshed token.

### Added

- `biometric_kyc.verify(use_enrolled_image=True, user_id=...)` verifies against the user's enrolled selfie; the grant is bound into the job's token and the selfie and liveness images may be omitted.

### Removed

- `use_enrolled_image` from `biometric.authenticate`; selfie and liveness images are now always required.

## [12.1.0] - 2026-10-01

### Added

- Residency Document Verification: `documents.verify_residency`.

## [12.0.0] - 2026-08-20

First public release of the Smile ID Python server SDK.

### Added

- Products: Enhanced KYC, Biometric KYC, Document Verification, Enhanced
  Document Verification, and SmartSelfie enrollment, authentication and
  comparison.
- Job status retrieval, with a `wait_until_complete` helper that polls until
  a job reaches a decision.
- Callback replay for completed jobs.
- User fraud reporting, with `flag_fraud` and `clear_fraud` convenience
  wrappers.
- Bank code, supported ID type and supported document lookups, and ID type
  availability checks.
- Sandbox and production environments, plus a `base_url` override for other
  Smile ID environments.
- A typed error hierarchy, covering client-side validation and every HTTP
  error the API returns.
- Automatic token management and retries for idempotent operations.

[Unreleased]: https://github.com/smileidentity/smileid-sdk-python/compare/v12.2.0...HEAD
[12.2.0]: https://github.com/smileidentity/smileid-sdk-python/compare/v12.1.0...v12.2.0
[12.1.0]: https://github.com/smileidentity/smileid-sdk-python/compare/v12.0.0...v12.1.0
[12.0.0]: https://github.com/smileidentity/smileid-sdk-python/releases/tag/v12.0.0
