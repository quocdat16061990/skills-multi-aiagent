#!/usr/bin/env python3
"""CLI orchestration; emits exactly one JSON object to stdout."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from content_classifier import classify_all, load_config
from email_report import build_email_content
from excel_report import write_report
from gmail_sender import send_gmail
from metrics import analyze
from youtube_collector import collect_channel


SKILL_DIR = Path(__file__).resolve().parent.parent


def runtime_root() -> Path:
    return Path(os.environ.get("OPENCLAW_RUNTIME_ROOT") or Path.home()).resolve()


def default_oauth_dir() -> Path:
    return Path(
        os.environ.get("OPENCLAW_GOOGLE_OAUTH_DIR")
        or runtime_root() / ".config/openclaw-google-calendar"
    ).resolve()


def default_client_json() -> Path:
    return Path(
        os.environ.get("OPENCLAW_GOOGLE_CLIENT_JSON")
        or runtime_root() / "AI_Runtime/client.json"
    ).resolve()


def parser() -> argparse.ArgumentParser:
    oauth_dir = default_oauth_dir()
    command = argparse.ArgumentParser(
        description="Phân tích YouTube, xuất Excel và tùy chọn gửi Gmail trong một lần chạy"
    )
    command.add_argument("url")
    command.add_argument("--limit", type=int, default=50, choices=range(1, 101), metavar="1-100")
    command.add_argument("--output-dir", default="./output")
    command.add_argument("--dry-run", action="store_true")
    command.add_argument("--config")
    command.add_argument("--email-to", help="Nếu có, gửi báo cáo sau khi tạo và xác minh workbook")
    command.add_argument("--email-subject")
    command.add_argument(
        "--client-json",
        type=Path,
        default=default_client_json(),
        help="Client OAuth dùng chung; mặc định RUNTIME_ROOT/AI_Runtime/client.json",
    )
    command.add_argument("--oauth-user-json", type=Path, default=oauth_dir / "oauth-user.json")
    command.add_argument(
        "--email-template",
        type=Path,
        default=SKILL_DIR / "assets/analysis_report_email_template.html",
    )
    return command


def run(args) -> dict:
    if args.email_to and not args.dry_run:
        client_path = args.client_json.expanduser().resolve()
        if not client_path.is_file() or not os.access(client_path, os.R_OK):
            raise FileNotFoundError(
                f"Không tìm thấy hoặc không đọc được client.json dùng chung: {client_path}"
            )
    config = load_config(args.config)
    collected = collect_channel(args.url, args.limit)
    rows = classify_all(collected["videos"], config)
    stats = analyze(rows)
    warnings = list(collected.get("warnings", []))
    result = {
        "status": "ok",
        "source": collected.get("source"),
        "counts": {
            "videos": len(rows),
            "shorts": sum(row["type"] == "short" for row in rows),
            "long_form": sum(row["type"] == "long-form" for row in rows),
        },
        "warnings": warnings,
        "output": None,
        "email": None,
    }
    if args.dry_run:
        result["dry_run"] = True
        result["preview"] = {"channel": collected["channel"], "metrics": stats}
        if args.email_to:
            result["email"] = {
                "status": "not_sent",
                "requested": True,
                "reason": "dry_run",
                "recipient": args.email_to,
            }
        return result

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc)
    stamp = generated_at.strftime("%Y%m%dT%H%M%SZ")
    workbook_path = output_dir / f"youtube_competitor_analysis_{stamp}.xlsx"
    write_report(workbook_path, collected["channel"], rows, stats, config, collected)
    result["output"] = str(workbook_path)

    if args.email_to:
        html_path = output_dir / f"youtube_competitor_email_{stamp}.html"
        _, text_body = build_email_content(
            args.email_template.expanduser().resolve(),
            html_path,
            collected["channel"],
            rows,
            stats,
            collected,
            workbook_path,
            generated_at,
        )
        subject = args.email_subject or (
            f"Báo cáo phân tích đối thủ YouTube – "
            f"{collected['channel'].get('title') or 'Kênh YouTube'} – "
            f"{generated_at.strftime('%d/%m/%Y')}"
        )
        result["email_html"] = str(html_path)
        try:
            result["email"] = send_gmail(
                args.client_json,
                args.oauth_user_json,
                args.email_to,
                subject,
                text_body,
                html_path,
                [workbook_path],
            )
        except Exception as error:
            result["status"] = "partial"
            result["email"] = {
                "status": "error",
                "error": type(error).__name__,
                "message": str(error),
                "recipient": args.email_to,
                "sent_verified": False,
            }
    return result


def main(argv=None) -> int:
    try:
        result = run(parser().parse_args(argv))
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0 if result.get("status") == "ok" else 1
    except Exception as error:
        print(
            json.dumps(
                {"status": "error", "error": type(error).__name__, "message": str(error)},
                ensure_ascii=False,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
