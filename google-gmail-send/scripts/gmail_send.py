#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import stat
from email.message import EmailMessage
from pathlib import Path

import requests

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


def checked_credential(value: Path, label: str) -> Path:
    path = value.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy {label}: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise PermissionError(f"{label} phải có quyền 0600: {path}")
    return path


def checked_file(value: str, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy {label}: {path}")
    return path


class GmailOAuth:
    def __init__(self, client_path: Path, oauth_user_path: Path) -> None:
        self.client_path = checked_credential(client_path, "client.json")
        self.oauth_user_path = checked_credential(oauth_user_path, "oauth-user.json")

    def access_token(self) -> str:
        client_payload = json.loads(self.client_path.read_text(encoding="utf-8"))
        client = client_payload.get("web") or client_payload.get("installed") or client_payload
        oauth_user = json.loads(self.oauth_user_path.read_text(encoding="utf-8"))
        refresh_token = oauth_user.get("refresh_token")
        if not refresh_token:
            raise ValueError("oauth-user.json không có refresh_token")
        response = requests.post(
            client.get("token_uri", "https://oauth2.googleapis.com/token"),
            data={
                "client_id": client["client_id"],
                "client_secret": client["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=30,
        )
        response.raise_for_status()
        refreshed = response.json()
        oauth_user.update(refreshed)
        oauth_user["refresh_token"] = refresh_token
        self.oauth_user_path.write_text(
            json.dumps(oauth_user, ensure_ascii=False),
            encoding="utf-8",
        )
        self.oauth_user_path.chmod(0o600)
        return refreshed["access_token"]

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token()}"}


def gmail_profile(oauth: GmailOAuth) -> None:
    response = requests.get(f"{GMAIL_API}/profile", headers=oauth.headers(), timeout=30)
    response.raise_for_status()
    payload = response.json()
    print(f"gmail_profile=ok messages_total={payload.get('messagesTotal', 0)}")


def html_content(path_value: str | None) -> str | None:
    if not path_value:
        return None
    path = checked_file(path_value, "file HTML")
    html = path.read_text(encoding="utf-8")
    lowered = html.casefold()
    if not html.strip():
        raise ValueError("File HTML rỗng")
    if "{{" in html or "}}" in html:
        raise ValueError("File HTML còn placeholder")
    if "<script" in lowered:
        raise ValueError("File HTML không được chứa JavaScript")
    return html


def attachment_paths(values: list[str]) -> list[Path]:
    return [checked_file(value, "file đính kèm") for value in values]


def payload_filenames(payload: dict) -> list[str]:
    filenames: list[str] = []

    def walk(part: dict) -> None:
        filename = part.get("filename")
        if filename:
            filenames.append(filename)
        for child in part.get("parts") or []:
            walk(child)

    walk(payload)
    return filenames


def send_email(
    oauth: GmailOAuth,
    recipient: str,
    subject: str,
    body: str,
    html_file: str | None,
    attachments: list[str],
) -> None:
    html = html_content(html_file)
    files = attachment_paths(attachments)
    message = EmailMessage()
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    if html is not None:
        message.add_alternative(html, subtype="html")
    for attachment in files:
        mime_type, _ = mimetypes.guess_type(attachment.name)
        main_type, sub_type = (mime_type or "application/octet-stream").split("/", 1)
        message.add_attachment(
            attachment.read_bytes(),
            maintype=main_type,
            subtype=sub_type,
            filename=attachment.name,
        )

    headers = oauth.headers()
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    response = requests.post(
        f"{GMAIL_API}/messages/send",
        headers={**headers, "Content-Type": "application/json"},
        json={"raw": raw},
        timeout=60,
    )
    response.raise_for_status()
    sent_message_id = response.json().get("id")
    if not sent_message_id:
        raise RuntimeError("Gmail chấp nhận request nhưng không trả message ID; không tự gửi lại")

    verification = requests.get(
        f"{GMAIL_API}/messages/{sent_message_id}",
        headers=headers,
        params={"format": "full"},
        timeout=30,
    )
    verification.raise_for_status()
    sent = verification.json()
    labels = set(sent.get("labelIds") or [])
    header_map = {
        header.get("name", "").casefold(): header.get("value", "")
        for header in sent.get("payload", {}).get("headers") or []
    }
    filenames = payload_filenames(sent.get("payload") or {})
    expected_filenames = [path.name for path in files]
    verified = (
        "SENT" in labels
        and recipient.casefold() in header_map.get("to", "").casefold()
        and subject == header_map.get("subject")
        and all(filename in filenames for filename in expected_filenames)
    )
    if not verified:
        raise RuntimeError("Email có thể đã gửi nhưng xác minh Sent chưa đạt; không tự gửi lại")
    print(f"gmail_send=ok sent_verified=true attachments={len(files)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Gửi Gmail cá nhân bằng OAuth")
    parser.add_argument("--client-json", required=True, type=Path)
    parser.add_argument("--oauth-user-json", required=True, type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("profile", help="Kiểm tra OAuth, không gửi email")
    send_parser = subparsers.add_parser("send", help="Gửi đúng một email")
    send_parser.add_argument("--to", required=True)
    send_parser.add_argument("--subject", required=True)
    send_parser.add_argument("--body", required=True, help="Nội dung text dự phòng")
    send_parser.add_argument("--html-file")
    send_parser.add_argument("--attachment", action="append", default=[])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    oauth = GmailOAuth(args.client_json, args.oauth_user_json)
    if args.command == "profile":
        gmail_profile(oauth)
    else:
        send_email(oauth, args.to, args.subject, args.body, args.html_file, args.attachment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
