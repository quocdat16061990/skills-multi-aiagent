"""Send one Gmail message via OAuth and verify the exact message in Sent."""
from __future__ import annotations

import base64
import json
import mimetypes
import stat
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import parseaddr
from pathlib import Path

import requests

GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"


def checked_credential(path_value: Path, label: str) -> Path:
    path = path_value.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy {label}: {path}")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise PermissionError(f"{label} phải có quyền 0600: {path}")
    return path


def access_token(client_json: Path, oauth_user_json: Path) -> str:
    client_path = checked_credential(client_json, "client.json")
    oauth_path = checked_credential(oauth_user_json, "oauth-user.json")
    client_payload = json.loads(client_path.read_text(encoding="utf-8"))
    client = client_payload.get("web") or client_payload.get("installed") or client_payload
    oauth_user = json.loads(oauth_path.read_text(encoding="utf-8"))
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
    oauth_path.write_text(json.dumps(oauth_user, ensure_ascii=False), encoding="utf-8")
    oauth_path.chmod(0o600)
    return refreshed["access_token"]


def validate_html(path: Path) -> str:
    html = path.read_text(encoding="utf-8")
    lowered = html.casefold()
    if not html.strip():
        raise ValueError("File HTML rỗng")
    if "{{" in html or "}}" in html:
        raise ValueError("File HTML còn placeholder")
    if "<script" in lowered or "@import" in lowered or "<link" in lowered:
        raise ValueError("HTML chứa tài nguyên hoặc mã không phù hợp Gmail")
    return html


def payload_filenames(payload: dict) -> list[str]:
    filenames: list[str] = []

    def walk(part: dict) -> None:
        if part.get("filename"):
            filenames.append(part["filename"])
        for child in part.get("parts") or []:
            walk(child)

    walk(payload)
    return filenames


def send_gmail(
    client_json: Path,
    oauth_user_json: Path,
    recipient: str,
    subject: str,
    text_body: str,
    html_path: Path,
    attachments: list[Path],
) -> dict:
    _, parsed_recipient = parseaddr(recipient)
    if not parsed_recipient or "@" not in parsed_recipient:
        raise ValueError("Địa chỉ email người nhận không hợp lệ")
    html = validate_html(html_path)
    checked_attachments = [path.expanduser().resolve() for path in attachments]
    for attachment in checked_attachments:
        if not attachment.is_file():
            raise FileNotFoundError(f"Không tìm thấy attachment: {attachment}")

    token = access_token(client_json, oauth_user_json)
    headers = {"Authorization": f"Bearer {token}"}
    profile = requests.get(f"{GMAIL_API}/profile", headers=headers, timeout=30)
    profile.raise_for_status()
    sender = profile.json().get("emailAddress")

    message = EmailMessage(policy=SMTP.clone(max_line_length=998))
    if sender:
        message["From"] = sender
    message["To"] = parsed_recipient
    message["Subject"] = subject
    message.set_content(text_body)
    message.add_alternative(html, subtype="html")
    for attachment in checked_attachments:
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
        headers={**headers, "Content-Type": "application/json"},
        json={"raw": raw},
        timeout=60,
    )
    response.raise_for_status()
    message_id = response.json().get("id")
    if not message_id:
        raise RuntimeError("Gmail chấp nhận request nhưng không trả message ID; không tự gửi lại")

    verification = requests.get(
        f"{GMAIL_API}/messages/{message_id}",
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
    verified_subject = str(make_header(decode_header(header_map.get("subject", ""))))
    filenames = payload_filenames(sent.get("payload") or {})
    expected_filenames = [attachment.name for attachment in checked_attachments]
    verified = (
        "SENT" in labels
        and parsed_recipient.casefold() in header_map.get("to", "").casefold()
        and subject == verified_subject
        and all(filename in filenames for filename in expected_filenames)
    )
    if not verified:
        raise RuntimeError("Email có thể đã gửi nhưng xác minh Sent chưa đạt; không tự gửi lại")
    return {
        "status": "ok",
        "sent_verified": True,
        "recipient": parsed_recipient,
        "subject": subject,
        "attachments": expected_filenames,
        "html": True,
        "text_fallback": True,
    }
