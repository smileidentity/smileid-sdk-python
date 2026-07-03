# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Removed

- The `partner_secret` option and HMAC request signing (the
  `SmileID-Timestamp` and `SmileID-Request-Signature` headers). Product
  decision: the provisional signing scheme confused partners for little
  benefit. It may be reintroduced if a signing contract is agreed.

### Security

- `base_url` must now be an absolute https URL with no query or fragment,
  validated at construction. There is deliberately no insecure override.
- `default_callback_url` and per-request `callback_url` values must be https;
  invalid values raise `ValidationError` before any request is sent.
- `job_id` and `user_id` path parameters are URL-encoded as single path
  segments before interpolation.
- Multipart part filenames and content types are sanitized against header
  injection (CR, LF, quotes).

### Changed

- Added `smileid.errors.UnexpectedResponseError`, raised when a success (2xx)
  response body is not a JSON object, with `status_code`, `raw_body` and
  `request_id` populated.

- Renamed the PyPI package from `smile-identity-core` to `smileid`, matching
  the importable module.
- Set the version to 12.0.0, aligning the server SDKs with the V12 mobile
  SDKs.

### Added

- Initial implementation of the V3 SDK: all 14 public operations under
  `client.<resource>.<verb>`, plus `flag_fraud` / `clear_fraud` wrappers.
- Automatic token management: fetch, thread-safe cache to expiry, one
  refresh-and-retry on 401.
- Typed error hierarchy under `smileid.errors`.
- Retry policy for idempotent operations with `Retry-After` support.
- `verifications.wait_until_complete` polling helper, `Consent` builder and
  client-side validation for user details and fraud reports.
