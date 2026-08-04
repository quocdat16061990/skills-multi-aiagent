#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from pathlib import Path
from urllib.parse import quote

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
RUNTIME_ROOT = Path(
    os.environ.get("OPENCLAW_RUNTIME_ROOT")
    or SKILL_DIR / "../../../.."
).resolve()
BASE = Path(
    os.environ.get("OPENCLAW_GOOGLE_SA_DIR")
    or RUNTIME_ROOT / ".config/openclaw-google-service-account"
).resolve()
SERVICE_ACCOUNT_FILE = BASE / "service-account.json"
CALENDAR_ENV = BASE / "calendar.env"
API_BASE = "https://www.googleapis.com/calendar/v3"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
TIMEZONE = "Asia/Ho_Chi_Minh"


def load_calendar_id(required=True):
    calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", "").strip()
    if not calendar_id and CALENDAR_ENV.exists():
        for raw in CALENDAR_ENV.read_text(encoding="utf-8").splitlines():
            if raw.startswith("GOOGLE_CALENDAR_ID="):
                calendar_id = raw.split("=", 1)[1].strip()
                break
    if required and not calendar_id:
        raise RuntimeError("Chưa có GOOGLE_CALENDAR_ID; chạy lệnh discover trước")
    return calendar_id


def session():
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
    )
    return AuthorizedSession(credentials)


def request(method, path, body=None, params=None):
    response = session().request(
        method,
        f"{API_BASE}/{path}",
        json=body,
        params=params,
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Google Calendar API HTTP {response.status_code}")
    if response.status_code == 204 or not response.content:
        return {}
    return response.json()


def calendar_path(calendar_id):
    return f"calendars/{quote(calendar_id, safe='')}"


def parse_time(value):
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone(dt.timedelta(hours=7)))
    return parsed


def event_summary(item):
    return {
        "id": item.get("id"),
        "summary": item.get("summary"),
        "start": item.get("start"),
        "end": item.get("end"),
        "status": item.get("status"),
    }


def discover():
    payload = request("GET", "users/me/calendarList", params={"maxResults": 250})
    writable = [
        item for item in payload.get("items", [])
        if item.get("accessRole") in {"owner", "writer"}
    ]
    if not writable:
        print("writable_calendars=0 selected=no")
        raise SystemExit(2)
    selected = next((item for item in writable if not item.get("primary")), writable[0])
    BASE.mkdir(parents=True, exist_ok=True)
    CALENDAR_ENV.write_text(f"GOOGLE_CALENDAR_ID={selected['id']}\n", encoding="utf-8")
    CALENDAR_ENV.chmod(0o600)
    print(f"writable_calendars={len(writable)} selected=yes")


def list_calendars():
    payload = request("GET", "users/me/calendarList", params={"maxResults": 250})
    output = [
        {
            "summary": item.get("summary"),
            "accessRole": item.get("accessRole"),
            "primary": bool(item.get("primary")),
            "timeZone": item.get("timeZone"),
        }
        for item in payload.get("items", [])
    ]
    print(json.dumps(output, ensure_ascii=False, indent=2))


def list_events(days):
    calendar_id = load_calendar_id()
    now = dt.datetime.now(dt.timezone.utc)
    end = now + dt.timedelta(days=days)
    payload = request(
        "GET",
        f"{calendar_path(calendar_id)}/events",
        params={
            "timeMin": now.isoformat(),
            "timeMax": end.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": 100,
        },
    )
    print(json.dumps([event_summary(item) for item in payload.get("items", [])], ensure_ascii=False, indent=2))


def create_event(summary, start, duration, description=None):
    calendar_id = load_calendar_id()
    start_time = parse_time(start)
    end_time = start_time + dt.timedelta(minutes=duration)
    body = {
        "summary": summary,
        "start": {"dateTime": start_time.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_time.isoformat(), "timeZone": TIMEZONE},
    }
    if description:
        body["description"] = description
    created = request("POST", f"{calendar_path(calendar_id)}/events", body=body)
    verified = request("GET", f"{calendar_path(calendar_id)}/events/{quote(created['id'], safe='')}")
    print(json.dumps(event_summary(verified), ensure_ascii=False, indent=2))


def update_event(event_id, summary=None, start=None, duration=60):
    calendar_id = load_calendar_id()
    body = {}
    if summary:
        body["summary"] = summary
    if start:
        start_time = parse_time(start)
        end_time = start_time + dt.timedelta(minutes=duration)
        body["start"] = {"dateTime": start_time.isoformat(), "timeZone": TIMEZONE}
        body["end"] = {"dateTime": end_time.isoformat(), "timeZone": TIMEZONE}
    request("PATCH", f"{calendar_path(calendar_id)}/events/{quote(event_id, safe='')}", body=body)
    verified = request("GET", f"{calendar_path(calendar_id)}/events/{quote(event_id, safe='')}")
    print(json.dumps(event_summary(verified), ensure_ascii=False, indent=2))


def delete_event(event_id):
    calendar_id = load_calendar_id()
    request("DELETE", f"{calendar_path(calendar_id)}/events/{quote(event_id, safe='')}")
    print("deleted=yes")


def test_permissions():
    calendar_id = load_calendar_id()
    start_time = dt.datetime.now(dt.timezone(dt.timedelta(hours=7))) + dt.timedelta(minutes=10)
    body = {
        "summary": "[TEST] OpenClaw Calendar Permission",
        "start": {"dateTime": start_time.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": (start_time + dt.timedelta(minutes=15)).isoformat(), "timeZone": TIMEZONE},
    }
    created = request("POST", f"{calendar_path(calendar_id)}/events", body=body)
    event_id = created["id"]
    request(
        "PATCH",
        f"{calendar_path(calendar_id)}/events/{quote(event_id, safe='')}",
        body={"summary": "[TEST] OpenClaw Calendar Permission Updated"},
    )
    request("GET", f"{calendar_path(calendar_id)}/events/{quote(event_id, safe='')}")
    request("DELETE", f"{calendar_path(calendar_id)}/events/{quote(event_id, safe='')}")
    print("calendar_create=ok calendar_update=ok calendar_delete=ok")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover")
    sub.add_parser("calendars")
    events_parser = sub.add_parser("events")
    events_parser.add_argument("--days", type=int, default=7)
    create_parser = sub.add_parser("create")
    create_parser.add_argument("summary")
    create_parser.add_argument("start")
    create_parser.add_argument("--duration", type=int, default=60)
    create_parser.add_argument("--description")
    update_parser = sub.add_parser("update")
    update_parser.add_argument("event_id")
    update_parser.add_argument("--summary")
    update_parser.add_argument("--start")
    update_parser.add_argument("--duration", type=int, default=60)
    delete_parser = sub.add_parser("delete")
    delete_parser.add_argument("event_id")
    sub.add_parser("test-permissions")
    args = parser.parse_args()
    if args.command == "discover":
        discover()
    elif args.command == "calendars":
        list_calendars()
    elif args.command == "events":
        list_events(args.days)
    elif args.command == "create":
        create_event(args.summary, args.start, args.duration, args.description)
    elif args.command == "update":
        update_event(args.event_id, args.summary, args.start, args.duration)
    elif args.command == "delete":
        delete_event(args.event_id)
    else:
        test_permissions()


if __name__ == "__main__":
    main()
