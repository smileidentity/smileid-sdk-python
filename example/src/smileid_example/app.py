from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Sequence, TextIO

import httpx
import smileid

Env = Callable[[str], Optional[str]]


class UsageError(Exception):
    """Raised for command-line usage errors."""


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        run(argv if argv is not None else sys.argv[1:])
        return 0
    except UsageError as exc:
        print(exc, file=sys.stderr)
        return 2


def run(
    argv: Sequence[str],
    *,
    getenv: Env = os.environ.get,
    stdout: TextIO = sys.stdout,
    http_client: Optional[httpx.Client] = None,
) -> None:
    config, command, args = parse_global_args(argv, getenv)
    if command in {"help", "-h", "--help"}:
        print_usage(stdout)
        return
    if command is None:
        raise UsageError("missing command; run one of: services, enhanced-kyc, status, replay")
    validate_config(config)

    with smileid.Client(
        partner_id=config["partner_id"],
        api_key=config["api_key"],
        partner_secret=config.get("partner_secret"),
        base_url=config.get("base_url"),
        default_callback_url=config.get("callback_url"),
        timeout=float(config["timeout"]),
        http_client=http_client,
    ) as client:
        if command == "services":
            run_services(client, args, stdout)
        elif command == "enhanced-kyc":
            run_enhanced_kyc(client, args, config, stdout)
        elif command == "status":
            run_status(client, args, stdout)
        elif command == "replay":
            run_replay(client, args, stdout)
        else:
            raise UsageError(f"unknown command {command}")


def parse_global_args(
    argv: Sequence[str],
    getenv: Env,
) -> tuple[Dict[str, str], Optional[str], Sequence[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--partner-id", default=getenv("SMILE_PARTNER_ID") or "")
    parser.add_argument("--api-key", default=getenv("SMILE_API_KEY") or "")
    parser.add_argument("--partner-secret", default=optional_env(getenv, "SMILE_PARTNER_SECRET"))
    parser.add_argument("--base-url", default=optional_env(getenv, "SMILE_BASE_URL"))
    parser.add_argument("--callback-url", default=optional_env(getenv, "SMILE_CALLBACK_URL"))
    parser.add_argument("--timeout", default=getenv("SMILE_TIMEOUT") or "30")
    namespace, rest = parser.parse_known_args(argv)
    return vars(namespace), (rest[0] if rest else None), rest[1:]


def optional_env(getenv: Env, key: str) -> Optional[str]:
    value = getenv(key)
    return value or None


def validate_config(config: Dict[str, str]) -> None:
    missing = []
    if not config["partner_id"]:
        missing.append("SMILE_PARTNER_ID or --partner-id")
    if not config["api_key"]:
        missing.append("SMILE_API_KEY or --api-key")
    if missing:
        raise UsageError(f"missing {' and '.join(missing)}")


def run_services(client: smileid.Client, args: Sequence[str], stdout: TextIO) -> None:
    parser = argparse.ArgumentParser(prog="services")
    parser.add_argument("--country", default="NG")
    opts = parser.parse_args(args)
    banks = client.services.bank_codes(country=opts.country)
    id_types = client.services.supported_id_types(country=opts.country)
    docs = client.services.supported_documents(country_code=opts.country)
    write_json(
        stdout,
        {
            "country": opts.country,
            "bank_codes": dump(banks)["bank_codes"],
            "id_types": dump(id_types)["id_types"],
            "documents": dump(docs)["valid_documents"],
        },
    )


def run_enhanced_kyc(
    client: smileid.Client,
    args: Sequence[str],
    config: Dict[str, str],
    stdout: TextIO,
) -> None:
    parser = argparse.ArgumentParser(prog="enhanced-kyc")
    parser.add_argument("--country", default="NG")
    parser.add_argument("--id-type", required=True)
    parser.add_argument("--id-number", required=True)
    parser.add_argument("--given-names", required=True)
    parser.add_argument("--last-name", required=True)
    parser.add_argument("--email")
    parser.add_argument("--phone-number")
    parser.add_argument("--privacy-url", default="https://example.com/privacy")
    parser.add_argument("--callback-url", default=config.get("callback_url"))
    opts = parser.parse_args(args)

    user_details = {
        "given_names": opts.given_names,
        "last_name": opts.last_name,
        **({"email": opts.email} if opts.email else {}),
        **({"phone_number": opts.phone_number} if opts.phone_number else {}),
    }
    accepted = client.enhanced_kyc.verify(
        country=opts.country,
        id_type=opts.id_type,
        id_number=opts.id_number,
        user_details=user_details,
        consent=smileid.Consent.granted(
            granted_at=datetime.now(timezone.utc),
            notice_language="EN",
            notice_privacy_policy_url=opts.privacy_url,
        ),
        callback_url=opts.callback_url,
    )
    write_json(
        stdout,
        {
            "status": accepted.status,
            "message": accepted.message,
            "job_id": accepted.job_id,
            "user_id": accepted.user_id,
            "accepted": accepted.is_accepted,
        },
    )


def run_status(client: smileid.Client, args: Sequence[str], stdout: TextIO) -> None:
    parser = argparse.ArgumentParser(prog="status")
    parser.add_argument("--job-id", required=True)
    opts = parser.parse_args(args)
    status = client.verifications.retrieve(opts.job_id)
    write_json(stdout, dump(status))


def run_replay(client: smileid.Client, args: Sequence[str], stdout: TextIO) -> None:
    parser = argparse.ArgumentParser(prog="replay")
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--callback-url")
    opts = parser.parse_args(args)
    replay = client.verifications.replay(opts.job_id, callback_url=opts.callback_url)
    write_json(stdout, dump(replay))


def dump(model: object) -> Dict[str, object]:
    return model.model_dump(mode="json")  # type: ignore[attr-defined]


def write_json(stdout: TextIO, value: object) -> None:
    stdout.write(json.dumps(value, indent=2))
    stdout.write("\n")


def print_usage(stdout: TextIO) -> None:
    stdout.write(
        """Usage:
  smileid-example-python [global flags] services --country NG
  smileid-example-python [global flags] enhanced-kyc --country NG --id-type NIN \
--id-number 12345678901 --given-names Amina --last-name Okafor \
--email amina@example.com --privacy-url https://example.com/privacy
  smileid-example-python [global flags] status --job-id job_...
  smileid-example-python [global flags] replay --job-id job_... --callback-url https://example.com/webhook

Global flags can also be set with SMILE_PARTNER_ID, SMILE_API_KEY,
SMILE_PARTNER_SECRET, SMILE_BASE_URL, SMILE_CALLBACK_URL and SMILE_TIMEOUT.
"""
    )
