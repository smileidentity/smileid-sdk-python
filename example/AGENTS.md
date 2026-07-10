# AGENTS.md

This repository is a standalone example application for the Smile ID Python SDK.

## Development rules

- Use only the public `smileid` SDK API.
- Keep tests deterministic with `httpx.MockTransport`; do not require real Smile ID credentials.
- Keep credentials out of source control and docs.
- Run `PYTHONPATH=src:.. pytest` before handing off changes.

## Layout

- `src/smileid_example/app.py` contains command parsing and SDK calls.
- `tests/test_app.py` is the SDK testbench.
- The parent SDK repository runs CI for this embedded example.
