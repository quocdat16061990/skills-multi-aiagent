from __future__ import annotations

import base64
import json
import mimetypes
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as datetime_time, timedelta
from pathlib import Path
from typing import Iterator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


API = "https://gmail.googleapis.com/gmail/v1/users/me"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ALLOWED_EXT = {".pdf", ".xml", ".jpg", ".jpeg", ".png", ".zip"}


@dataclass(frozen=True)
class Attachment:
    message_id: str = field(repr=False)
    attachment_id: str = field(repr=False)
    internal_date: str
    subject: str
    sender: str
    filename: str
    mime_type: str
    size: int


class GmailReader:
    def __init__(self, client_json: Path, oauth_user_json: Path, timeout: int = 30):
        self.client_path = client_json
        self.oauth_user_path = oauth_user_json
        self.timeout = timeout
        self.client = json.loads(client_json.read_text(encoding="utf-8"))
        self.oauth_user = json.loads(oauth_user_json.read_text(encoding="utf-8"))
        self.session = requests.Session()
        self._refresh()

    def _refresh(self) -> None:
        config = self.client.get("installed") or self.client.get("web") or {}
        refresh_token = self.oauth_user.get("refresh_token")
        if not refresh_token or not config.get("client_id") or not config.get("client_secret"):
            raise RuntimeError("OAuth client/user credential files lack refresh credentials")
        response = requests.post(
            config.get("token_uri", TOKEN_URL),
            data={
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        refreshed = response.json()
        self.oauth_user["access_token"] = refreshed["access_token"]
        self.oauth_user["expires_at"] = int(time.time()) + int(refreshed.get("expires_in", 3600))
        if refreshed.get("refresh_token"):
            self.oauth_user["refresh_token"] = refreshed["refresh_token"]
        self.oauth_user_path.write_text(
            json.dumps(self.oauth_user, indent=2),
            encoding="utf-8",
        )
        self.oauth_user_path.chmod(0o600)
        self.session.headers["Authorization"] = "Bearer " + self.oauth_user["access_token"]

    def _get(self, path: str, params: dict | None = None) -> dict:
        response = self.session.get(API + path, params=params, timeout=self.timeout)
        if response.status_code == 401:
            self._refresh()
            response = self.session.get(API + path, params=params, timeout=self.timeout)
        if not response.ok:
            raise RuntimeError(f"Gmail API request failed with HTTP {response.status_code}")
        return response.json()

    @staticmethod
    def query(start: date, end: date, timezone_name: str) -> str:
        if end < start:
            raise ValueError("end date precedes start date")
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {timezone_name}") from exc
        start_at = datetime.combine(start, datetime_time.min, tzinfo=timezone)
        end_at = datetime.combine(end + timedelta(days=1), datetime_time.min, tzinfo=timezone)
        return f"in:inbox after:{int(start_at.timestamp())} before:{int(end_at.timestamp())} has:attachment"

    def messages(self, start: date, end: date, timezone_name: str) -> Iterator[dict]:
        page_token = None
        while True:
            params = {
                "q": self.query(start, end, timezone_name),
                "labelIds": "INBOX",
                "maxResults": 500,
            }
            if page_token:
                params["pageToken"] = page_token
            page = self._get("/messages", params)
            for item in page.get("messages", []):
                yield self._get("/messages/" + item["id"], {"format": "full"})
            page_token = page.get("nextPageToken")
            if not page_token:
                break

    @staticmethod
    def _parts(part: dict) -> Iterator[dict]:
        yield part
        for child in part.get("parts", []):
            yield from GmailReader._parts(child)

    def attachments(self, message: dict) -> Iterator[Attachment]:
        headers = {
            header.get("name", "").lower(): header.get("value", "")
            for header in message.get("payload", {}).get("headers", [])
        }
        for part in self._parts(message.get("payload", {})):
            name = Path(part.get("filename") or "").name
            body = part.get("body", {})
            if name and Path(name).suffix.lower() in ALLOWED_EXT and body.get("attachmentId"):
                yield Attachment(
                    message_id=message["id"],
                    attachment_id=body["attachmentId"],
                    internal_date=message.get("internalDate", ""),
                    subject=headers.get("subject", ""),
                    sender=headers.get("from", ""),
                    filename=name,
                    mime_type=part.get(
                        "mimeType",
                        mimetypes.guess_type(name)[0] or "application/octet-stream",
                    ),
                    size=int(body.get("size", 0)),
                )

    def download(self, attachment: Attachment, max_bytes: int) -> bytes:
        if attachment.size > max_bytes:
            raise ValueError("attachment exceeds size limit")
        payload = self._get(
            f"/messages/{attachment.message_id}/attachments/{attachment.attachment_id}"
        )
        raw = payload.get("data", "")
        data = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if len(data) > max_bytes:
            raise ValueError("attachment exceeds size limit")
        return data


def safe_filename(name: str) -> str:
    name = Path(name).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name[:180] or "attachment"
