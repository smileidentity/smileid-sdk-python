# Security Policy

## Reporting a vulnerability

If you believe you have found a security vulnerability in this SDK, please report it privately rather than opening a public issue.

**Email:** [security@smileidentity.com](mailto:security@smileidentity.com)

Please include:

- A description of the issue and its potential impact.
- Steps to reproduce, or a proof-of-concept if available.
- Any relevant code samples or logs (with sensitive data redacted).
- Your contact details, so we can follow up.

We aim to acknowledge reports within **3 business days** and to provide a substantive response within **10 business days**. Please give us a reasonable opportunity to address the issue before any public disclosure.

## Scope

This repository contains the Smile ID server-side SDK for Python: source code, tests, and packaging configuration. Reports relating to the following are in scope and welcome:

- Vulnerabilities in the SDK's source code (for example, insecure handling of credentials, request signing, or file uploads).
- Vulnerabilities introduced by the SDK's dependencies.
- Issues affecting the integrity of this repository (for example, supply-chain concerns in CI workflows or the package publishing process).
- Vulnerabilities in the deployed Smile Identity API endpoints that this SDK calls.

## Out of scope

- Vulnerabilities in third-party services we link to (please report those to the relevant vendor).
- Findings that require physical access, social engineering, or DoS testing against production endpoints.
