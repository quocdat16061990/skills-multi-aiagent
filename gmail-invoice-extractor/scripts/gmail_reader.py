from __future__ import annotations

import base64, json, mimetypes, re, time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator
import requests

API = "https://gmail.googleapis.com/gmail/v1/users/me"
TOKEN_URL = "https://oauth2.googleapis.com/token"
ALLOWED_EXT = {".pdf", ".xml", ".jpg", ".jpeg", ".png", ".zip"}

@dataclass
class Attachment:
    message_id: str
    thread_id: str
    internal_date: str
    subject: str
    sender: str
    filename: str
    mime_type: str
    attachment_id: str
    size: int

class GmailReader:
    def __init__(self, client_json: Path, token_json: Path, timeout: int = 30):
        self.client_path, self.token_path, self.timeout = client_json, token_json, timeout
        self.client = json.loads(client_json.read_text(encoding="utf-8"))
        self.token = json.loads(token_json.read_text(encoding="utf-8"))
        self.session = requests.Session()
        self._refresh()

    def _refresh(self) -> None:
        cfg = self.client.get("installed") or self.client.get("web") or {}
        refresh = self.token.get("refresh_token")
        if not refresh or not cfg.get("client_id") or not cfg.get("client_secret"):
            raise RuntimeError("OAuth client/token files lack refresh credentials")
        r = requests.post(cfg.get("token_uri", TOKEN_URL), data={"client_id": cfg["client_id"], "client_secret": cfg["client_secret"], "refresh_token": refresh, "grant_type": "refresh_token"}, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        self.token["access_token"] = data["access_token"]
        self.token["expires_at"] = int(time.time()) + int(data.get("expires_in", 3600))
        if data.get("refresh_token"):
            self.token["refresh_token"] = data["refresh_token"]
        self.token_path.write_text(json.dumps(self.token, indent=2), encoding="utf-8")
        self.session.headers["Authorization"] = "Bearer " + self.token["access_token"]

    def _get(self, path: str, params=None) -> dict:
        r = self.session.get(API + path, params=params, timeout=self.timeout)
        if r.status_code == 401:
            self._refresh(); r = self.session.get(API + path, params=params, timeout=self.timeout)
        r.raise_for_status(); return r.json()

    @staticmethod
    def query(start: date, end: date) -> str:
        if end < start: raise ValueError("end date precedes start date")
        return f"after:{(start-timedelta(days=1)):%Y/%m/%d} before:{(end+timedelta(days=1)):%Y/%m/%d} has:attachment"

    def messages(self, start: date, end: date) -> Iterator[dict]:
        token = None
        while True:
            p = {"q": self.query(start, end), "maxResults": 500}
            if token: p["pageToken"] = token
            page = self._get("/messages", p)
            for item in page.get("messages", []):
                yield self._get("/messages/" + item["id"], {"format": "full"})
            token = page.get("nextPageToken")
            if not token: break

    @staticmethod
    def _parts(part: dict) -> Iterator[dict]:
        yield part
        for child in part.get("parts", []): yield from GmailReader._parts(child)

    def attachments(self, message: dict) -> Iterator[Attachment]:
        headers = {h.get("name", "").lower(): h.get("value", "") for h in message.get("payload", {}).get("headers", [])}
        for p in self._parts(message.get("payload", {})):
            name = Path(p.get("filename") or "").name
            body = p.get("body", {})
            if name and Path(name).suffix.lower() in ALLOWED_EXT and body.get("attachmentId"):
                yield Attachment(message["id"], message.get("threadId", ""), message.get("internalDate", ""), headers.get("subject", ""), headers.get("from", ""), name, p.get("mimeType", mimetypes.guess_type(name)[0] or "application/octet-stream"), body["attachmentId"], int(body.get("size", 0)))

    def download(self, a: Attachment, max_bytes: int) -> bytes:
        if a.size > max_bytes: raise ValueError("attachment exceeds size limit")
        obj = self._get(f"/messages/{a.message_id}/attachments/{a.attachment_id}")
        raw = obj.get("data", "")
        data = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if len(data) > max_bytes: raise ValueError("attachment exceeds size limit")
        return data

def safe_filename(name: str) -> str:
    name = Path(name).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name[:180] or "attachment"
