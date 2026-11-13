# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- AML screening: `aml.screen` (`POST /v3/aml`) and `aml.screen_sync` (`POST /v3/aml/sync`), which returns a `OneTimeAmlResult` and accepts an `idempotency_key`.
- AML Monitoring: `aml.monitor` (`POST /v3/aml/monitoring`) and `aml.monitoring_news` (`GET /v3/aml/monitoring/{job_id}/news/{reference}`).
- The `OneTimeAmlResult` and `AmlMonitoringNewsResponse` response models.

## [13.0.0] - 2026-11-09

This is a major version because it changes the public API of 12.1.0. Version 12.2.0 was never published; its changes ship here.

### Breaking changes

- `biometric.authenticate` no longer takes `use_enrolled_image` and requires `selfie_image` and `liveness_images`. Pass both images, or use `biometric_kyc.verify(use_enrolled_image=True, user_id=...)` to check against an enrolled selfie.
- A `user_id` that is empty or padded with whitespace raises `ValidationError`. Strip user IDs before you pass them.
- The `usesmileid.client.auth` module and `Transport.token_manager` are removed, because each request now mints its own token. Remove any code that reads or refreshes the cached token.
- The request builders in `usesmileid.generated.operations` changed to match: `authentication` requires both images, and `biometric_kyc` no longer takes `use_enrolled_image`. Call the client methods instead of the builders.

### Changed

- Each request mints its own token, bound to that request's `user_id` and product, instead of reusing one cached token. A 401 is no longer retried with a refreshed token.
- A `user_id` that is empty or padded with whitespace raises `ValidationError` before any request is sent.
- `biometric.authenticate` takes `selfie_image` and `liveness_images` as required arguments.

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

[Unreleased]: https://github.com/smileidentity/smileid-sdk-python/compare/v13.0.0...HEAD
[13.0.0]: https://github.com/smileidentity/smileid-sdk-python/compare/v12.1.0...v13.0.0
[12.1.0]: https://github.com/smileidentity/smileid-sdk-python/compare/v12.0.0...v12.1.0
[12.0.0]: https://github.com/smileidentity/smileid-sdk-python/releases/tag/v12.0.0
