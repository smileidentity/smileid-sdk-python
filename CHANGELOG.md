# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

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
- Optional HMAC request signing (off unless `partner_secret` is set;
  construction provisional).
