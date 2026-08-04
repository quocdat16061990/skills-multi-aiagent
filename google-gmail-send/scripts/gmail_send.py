#!/usr/bin/env python3
import argparse
import base64
import json
import mimetypes
import os
from email.message import EmailMessage
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
RUNTIME_ROOT = Path(
    os.environ.get("OPENCLAW_RUNTIME_ROOT")
    or SKILL_DIR / "../../../.."
).resolve()
BASE = Path(
    os.environ.get("OPENCLAW_GOOGLE_OAUTH_DIR")
    or RUNTIME_ROOT / ".config/openclaw-google-calendar"
).resolve()
CLIENT_FILE = BASE / "client.json"
TOKEN_FILE = BASE / "token.json"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


def access_token():
    client_payload = json.loads(CLIENT_FILE.read_text(encoding="utf-8"))
    client = client_payload.get("web") or client_payload.get("installed") or client_payload
    token = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    if token.get("refresh_token"):
        response = requests.post(
            client.get("token_uri", "https://oauth2.googleapis.com/token"),
            data={
                "client_id": client["client_id"],
                "client_secret": client["client_secret"],
                "refresh_token": token["refresh_token"],
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        response.raise_for_status()
        token.update(response.json())
        TOKEN_FILE.write_text(json.dumps(token), encoding="utf-8")
        TOKEN_FILE.chmod(0o600)
    return token["access_token"]


def headers():
    return {"Authorization": f"Bearer {access_token()}"}


def profile():
    response = requests.get(f"{GMAIL_API}/profile", headers=headers(), timeout=30)
    response.raise_for_status()
    payload = response.json()
    print(f"gmail_profile=ok messages_total={payload.get('messagesTotal', 0)}")


def checked_file(value, label):
    path = Path(value)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy {label}: {path}")
    return path


def send_email(recipient, subject, body, html_file, attachments):
    message = EmailMessage()
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    if html_file:
        html_path = checked_file(html_file, "file HTML")
        html = html_path.read_text(encoding="utf-8")
        if not html.strip():
            raise ValueError("File HTML rỗng")
        message.add_alternative(html, subtype="html")

    for attachment_value in attachments:
        attachment = checked_file(attachment_value, "file đính kèm")
        mime_type, _ = mimetypes.guess_type(attachment.name)
        main_type, sub_type = (mime_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            attachment.read_bytes(),
            maintype=main_type,
            subtype=sub_type,
            filename=attachment.name,
        )

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    response = requests.post(
        f"{GMAIL_API}/messages/send",
        headers={**headers(), "Content-Type": "application/json"},
        json={"raw": raw},
        timeout=60,
    )
    response.raise_for_status()
    print("gmail_send=ok")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("profile")
    send_parser = sub.add_parser("send")
    send_parser.add_argument("--to", required=True)
    send_parser.add_argument("--subject", required=True)
    send_parser.add_argument("--body", required=True, help="Bản text dự phòng")
    send_parser.add_argument("--html-file")
    send_parser.add_argument("--attachment", action="append", default=[])
    args = parser.parse_args()
    if args.command == "profile":
        profile()
    else:
        send_email(args.to, args.subject, args.body, args.html_file, args.attachment)


if __name__ == "__main__":
    main()
