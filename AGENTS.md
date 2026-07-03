# Agent notes

This repository holds Smile ID's V3 server-side SDK for Python (PyPI package and importable module are both `smileid`).

## Source of truth

The API surface (endpoints, request and response shapes) is defined by the OpenAPI specs at [smileidentity/api-reference](https://github.com/smileidentity/api-reference). Treat that repository as authoritative when generating or reviewing client code — do not invent endpoints or fields that aren't described there.

## Layout

- `smileid/generated/` — generator-owned code, produced from the OpenAPI specs. Do not hand-edit files here once the generator is wired up.
- `smileid/client/` — hand-written client code (configuration, request signing, transport).
- `smileid/errors/` — hand-written error types.
- `smileid/helpers/` — hand-written convenience helpers.

Auth token lifecycle, transport, retries, serialization and errors are hand-written and must survive a future generator run; only `smileid/generated/` may be regenerated.

All tests are offline (respx mocks) except `tests/test_e2e_sandbox.py`, which reads `SMILE_PARTNER_ID` and `SMILE_API_KEY` from the environment and skips when they are unset.

## Running tests

```bash
python -m pytest
```

Lint with `ruff check .` and type-check with `mypy smileid`.

## Org-wide conventions

Org-wide agent conventions for Smile ID repositories live at [smileidentity/agents](https://github.com/smileidentity/agents) (private repository, internal contributors only).
