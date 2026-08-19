# Smile ID Python SDK Example

This repository is a small CLI application that demonstrates the public `usesmileid` Python SDK.

It also acts as a testbench: tests run the same CLI code against `httpx.MockTransport` and verify the SDK sends the expected requests.

## Requirements

- Python 3.8 or later.
- Smile ID sandbox credentials for real API calls.

## Setup

During SDK development, install the sibling SDK checkout and this example:

```bash
python -m pip install -e ..
python -m pip install -e ".[dev]"
```

## Configuration

```bash
export SMILE_PARTNER_ID="12345"
export SMILE_API_KEY="..."
export SMILE_CALLBACK_URL="https://your-app.example.com/smile-callback"
```

Partner IDs are displayed zero-padded in the portal (for example `002`) but must be passed without leading zeros (`2`).

`SMILE_BASE_URL` points the SDK at a specific Smile ID environment. The only named environments are sandbox (the default) and production, so use this to reach anything else:

```bash
export SMILE_BASE_URL="https://devapi.smileidentity.com"
```

Optional:

- `SMILE_TIMEOUT` sets the per-request timeout in seconds.

## Commands

```bash
python -m smileid_example services --country NG
python -m smileid_example enhanced-kyc --country NG --id-type NIN --id-number 12345678901 --given-names "Amina Fatou" --last-name Clearwater --email amina.clearwater@example.com --privacy-url https://your-app.example.com/privacy
python -m smileid_example status --job-id job_...
python -m smileid_example replay --job-id job_... --callback-url https://your-app.example.com/smile-callback
```

Non-production environments match test identities on given names, last name and email. An identity they do not recognise resolves to `block`.

`status` reports `processing` while the job runs, then the decision itself — `clear`, `block`, `attention` or `error`:

```json
{
  "status": "clear",
  "job_id": "job_...",
  "user_id": "user_...",
  "message": "Job completed"
}
```

## Development

```bash
PYTHONPATH=src:.. pytest
PYTHONPATH=src:.. mypy src
ruff check .
```
