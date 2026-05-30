#!/usr/bin/env python3
"""Prepare or send WhatsApp digest messages for configured users."""
import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .persona_digest import BASE_URL, whatsapp_summary


DEFAULT_RECIPIENTS = Path.home() / ".config" / "knowledge-os" / "whatsapp-recipients.json"


@dataclass(frozen=True)
class PreparedMessage:
    user_id: str
    phone: str
    digest_path: str
    website_url: str
    item_count: int
    message: str
    skipped: bool = False


def parse_user_ids(users: Optional[str], repeated_users: Optional[Sequence[str]] = None) -> List[str]:
    """Parse comma-separated and repeated user arguments into a stable unique list."""
    ordered: List[str] = []
    for raw in list(repeated_users or []) + ([users] if users else []):
        for user_id in raw.split(","):
            normalized = user_id.strip()
            if normalized and normalized not in ordered:
                ordered.append(normalized)
    return ordered


def load_recipients(path: str) -> Dict[str, str]:
    """Load a local user-id to phone-number map."""
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Recipients file must contain a JSON object: {path}")

    recipients: Dict[str, str] = {}
    for user_id, phone in data.items():
        if not isinstance(user_id, str) or not isinstance(phone, str) or not phone.strip():
            raise ValueError("Recipients must be string user IDs mapped to non-empty phone strings")
        recipients[user_id] = phone.strip()
    return recipients


def prepare_messages(
    user_ids: Iterable[str],
    recipients: Dict[str, str],
    digest_path: str,
    users_dir: str = "configs/users",
    base_url: Optional[str] = None,
    skip_empty: bool = False,
) -> List[PreparedMessage]:
    """Build WhatsApp messages for users from one canonical persona digest."""
    digest = Path(digest_path)
    if not digest.is_file():
        raise FileNotFoundError(f"Digest not found: {digest_path}")

    prepared: List[PreparedMessage] = []
    for user_id in user_ids:
        if user_id not in recipients:
            raise KeyError(f"No recipient phone configured for user: {user_id}")
        user_config_path = Path(users_dir) / f"{user_id}.json"
        if not user_config_path.is_file():
            raise FileNotFoundError(f"User config not found: {user_config_path}")

        summary = whatsapp_summary(
            user_config_path=str(user_config_path),
            digest_path=str(digest),
            base_url=base_url,
        )
        item_count = int(summary["item_count"])
        prepared.append(PreparedMessage(
            user_id=user_id,
            phone=recipients[user_id],
            digest_path=str(digest),
            website_url=summary["website_url"],
            item_count=item_count,
            message=summary["message"],
            skipped=skip_empty and item_count == 0,
        ))
    return prepared


def build_sender_args(send_command: str, phone: str, message: str) -> List[str]:
    """Build argv for a local sender command.

    If placeholders are present, replace them. Otherwise append the common
    `--to PHONE --message MESSAGE` shape used in the README.
    """
    args = shlex.split(send_command)
    if not args:
        raise ValueError("send_command must not be empty")

    has_phone_placeholder = any("{phone}" in arg for arg in args)
    has_message_placeholder = any("{message}" in arg for arg in args)
    if has_phone_placeholder or has_message_placeholder:
        return [
            arg.replace("{phone}", phone).replace("{message}", message)
            for arg in args
        ]
    return args + ["--to", phone, "--message", message]


def send_message(send_command: str, prepared: PreparedMessage) -> None:
    args = build_sender_args(send_command, prepared.phone, prepared.message)
    try:
        subprocess.run(args, check=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Sender executable not found: {args[0]}. "
            "Install it or pass --send-command with the full sender command."
        ) from exc


def print_prepared(prepared: Sequence[PreparedMessage], send: bool) -> None:
    for item in prepared:
        status = "skipped" if item.skipped else ("sent" if send else "dry_run")
        print(f"user: {item.user_id}")
        print(f"status: {status}")
        print(f"phone: {item.phone}")
        print(f"digest_path: {item.digest_path}")
        print(f"website_url: {item.website_url}")
        print(f"item_count: {item.item_count}")
        print("")
        print(item.message)
        print("")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare or send WhatsApp digest messages.")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--digest", help="Digest markdown path; defaults to knos-digest/<date>.md")
    parser.add_argument("--users", help="Comma-separated user IDs; defaults to vb,kintu,mikey")
    parser.add_argument("--user", action="append", dest="repeated_users", help="User ID; may be repeated")
    parser.add_argument("--users-dir", default="configs/users")
    parser.add_argument("--recipients", default=str(DEFAULT_RECIPIENTS))
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--send-command", default=os.environ.get("WHATSAPP_SEND_COMMAND", ""))
    parser.add_argument("--send", action="store_true", help="Actually call the configured sender command")
    parser.add_argument("--dry-run", action="store_true", help="Print messages without sending")
    parser.add_argument("--include-empty", action="store_true", help="Deprecated; zero-item messages are sent by default")
    parser.add_argument("--skip-empty", action="store_true", help="Skip zero-item messages")
    args = parser.parse_args()

    user_ids = parse_user_ids(args.users, args.repeated_users)
    if not user_ids:
        user_ids = parse_user_ids("vb,kintu,mikey")
    if not user_ids:
        parser.error("At least one user is required")
    if args.send and args.dry_run:
        parser.error("--send and --dry-run cannot both be set")
    if args.send and not args.send_command:
        parser.error("--send requires --send-command or WHATSAPP_SEND_COMMAND")

    digest_path = args.digest or str(Path("knos-digest") / f"{args.date}.md")
    try:
        recipients = load_recipients(args.recipients)
        prepared = prepare_messages(
            user_ids=user_ids,
            recipients=recipients,
            digest_path=digest_path,
            users_dir=args.users_dir,
            base_url=args.base_url,
            skip_empty=args.skip_empty,
        )
        if args.send:
            for item in prepared:
                if item.skipped:
                    continue
                send_message(args.send_command, item)
        print_prepared(prepared, send=args.send)
    except KeyError as exc:
        missing = str(exc).strip("'")
        print(f"whatsapp_delivery: {missing}", file=sys.stderr)
        print(f"recipients_file: {args.recipients}", file=sys.stderr)
        print("Add that user to the recipients file or pass --users/--user to deliver only configured users.", file=sys.stderr)
        raise SystemExit(1)
    except Exception as exc:
        print(f"whatsapp_delivery: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
