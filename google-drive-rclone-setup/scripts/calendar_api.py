#!/usr/bin/env python3
"""Minimal Google Calendar helper. Keeps credentials out of stdout."""
import argparse, datetime as dt, json, os, pathlib, urllib.parse, urllib.request

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
RUNTIME_ROOT = pathlib.Path(
    os.environ.get('OPENCLAW_RUNTIME_ROOT')
    or SKILL_DIR/'../../../..'
).resolve()
BASE = pathlib.Path(
    os.environ.get('OPENCLAW_CALENDAR_DIR')
    or RUNTIME_ROOT/'.config/openclaw-google-calendar'
).resolve()
CLIENT = BASE/'client.json'; TOKEN = BASE/'token.json'
TZ = 'Asia/Ho_Chi_Minh'

def load():
    raw = json.loads(CLIENT.read_text())
    c = raw.get('web') or raw.get('installed')
    if not c:
        raise RuntimeError('client.json must contain web or installed OAuth client')
    t = json.loads(TOKEN.read_text())
    if 'refresh_token' in t:
        data = urllib.parse.urlencode({'client_id': c['client_id'], 'client_secret': c['client_secret'], 'refresh_token': t['refresh_token'], 'grant_type': 'refresh_token'}).encode()
        req = urllib.request.Request(c.get('token_uri', '${GOOGLE_TOKEN_URI}'), data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
        with urllib.request.urlopen(req, timeout=30) as r:
            t.update(json.load(r))
        TOKEN.write_text(json.dumps(t)); TOKEN.chmod(0o600)
    return t['access_token']

def call(method, path, body=None):
    req = urllib.request.Request('https://www.googleapis.com/calendar/v3/' + path, method=method, headers={'Authorization': 'Bearer ' + load(), 'Content-Type': 'application/json'})
    if body is not None:
        req.data = json.dumps(body, ensure_ascii=False).encode()
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r) if r.status != 204 else {}

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('calendars'); sub.add_parser('events')
    x = sub.add_parser('create'); x.add_argument('summary'); x.add_argument('start'); x.add_argument('--duration', type=int, default=60)
    d = sub.add_parser('delete'); d.add_argument('event_id')
    a = ap.parse_args()
    if a.cmd == 'calendars':
        out = call('GET', 'users/me/calendarList?maxResults=250'); print(json.dumps([{'id': i.get('id'), 'summary': i.get('summary'), 'timeZone': i.get('timeZone')} for i in out.get('items', [])], ensure_ascii=False, indent=2))
    elif a.cmd == 'events':
        out = call('GET', 'calendars/primary/events?maxResults=50&singleEvents=true&orderBy=startTime'); print(json.dumps(out.get('items', []), ensure_ascii=False, indent=2))
    elif a.cmd == 'create':
        start = dt.datetime.fromisoformat(a.start); end = start + dt.timedelta(minutes=a.duration)
        out = call('POST', 'calendars/primary/events', {'summary': a.summary, 'start': {'dateTime': start.isoformat(), 'timeZone': TZ}, 'end': {'dateTime': end.isoformat(), 'timeZone': TZ}})
        print(json.dumps({'id': out.get('id'), 'summary': out.get('summary'), 'start': out.get('start'), 'end': out.get('end')}, ensure_ascii=False, indent=2))
    else:
        call('DELETE', 'calendars/primary/events/' + urllib.parse.quote(a.event_id, safe='')); print('deleted')

if __name__ == '__main__': main()
