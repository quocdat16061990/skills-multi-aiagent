#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from email.utils import parseaddr
from pathlib import Path

from excel_report import write_report
from gmail_reader import Attachment, GmailReader, safe_filename
from invoice_parser import Invoice, parse_document
from safe_archive import extract_zip


def iso(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def normalized_search(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "", without_marks.casefold())


def normalized_sender(value: str) -> str:
    address = parseaddr(value or "")[1]
    return (address or value or "").strip().casefold()


def public_internal_date(value: str) -> str:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def attachment_row(message_index: int, item: Attachment, digest: str, path: Path) -> dict:
    return {
        "message_index": message_index,
        "received_at_utc": public_internal_date(item.internal_date),
        "subject": item.subject,
        "sender": item.sender,
        "filename": item.filename,
        "mime_type": item.mime_type,
        "size": item.size,
        "sha256": digest,
        "saved_path": str(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read Gmail invoice attachments and build a review workbook"
    )
    parser.add_argument("--start-date", required=True, type=iso)
    parser.add_argument("--end-date", required=True, type=iso)
    parser.add_argument("--timezone", default="Asia/Ho_Chi_Minh")
    parser.add_argument("--client-json", required=True, type=Path)
    parser.add_argument("--oauth-user-json", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--max-attachment-bytes", type=int, default=25_000_000)
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")

    reader = GmailReader(args.client_json, args.oauth_user_json)
    found: list[tuple[int, Attachment]] = []
    message_count = 0
    for message_count, message in enumerate(
        reader.messages(args.start_date, args.end_date, args.timezone),
        1,
    ):
        found.extend((message_count, item) for item in reader.attachments(message))

    if args.dry_run:
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "timezone": args.timezone,
                    "messages": message_count,
                    "attachments": len(found),
                    "items": [
                        {
                            "attachment_index": index,
                            "message_index": message_index,
                            "filename": item.filename,
                            "mime_type": item.mime_type,
                            "size": item.size,
                        }
                        for index, (message_index, item) in enumerate(found, 1)
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 0

    root = args.output_dir.resolve()
    if root.exists() and any(root.iterdir()):
        raise RuntimeError("output directory must be new or empty")
    raw_dir = root / "attachments"
    unpacked_dir = root / "unzipped"
    raw_dir.mkdir(parents=True, exist_ok=True)
    unpacked_dir.mkdir(parents=True, exist_ok=True)

    invoices: list[dict] = []
    attachment_rows: list[dict] = []
    duplicates: list[dict] = []
    errors: list[dict] = []
    sha_seen: dict[str, str] = {}
    business_seen: dict[tuple[str, str], str] = {}
    known_invoices: list[tuple[Invoice, Path, Attachment]] = []
    unparsed: list[tuple[Invoice, Path, Attachment]] = []

    for attachment_index, (message_index, item) in enumerate(found, 1):
        try:
            data = reader.download(item, args.max_attachment_bytes)
            digest = hashlib.sha256(data).hexdigest()
            if digest in sha_seen:
                duplicates.append(
                    {
                        "kind": "sha256",
                        "value": digest,
                        "source": item.filename,
                        "duplicate_of": sha_seen[digest],
                        "confidence": "high",
                    }
                )
                continue
            sha_seen[digest] = item.filename
            folder = raw_dir / f"message_{message_index:04d}"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"{attachment_index:04d}_{safe_filename(item.filename)}"
            path.write_bytes(data)
            attachment_rows.append(attachment_row(message_index, item, digest, path))
            documents = (
                extract_zip(data, unpacked_dir / f"attachment_{attachment_index:04d}")
                if path.suffix.lower() == ".zip"
                else [path]
            )
            for document in documents:
                try:
                    invoice = parse_document(document, args.ocr)
                    if not invoice.is_candidate():
                        unparsed.append((invoice, document, item))
                        continue
                    business_key = invoice.business_key()
                    if business_key and business_key in business_seen:
                        duplicates.append(
                            {
                                "kind": business_key[0],
                                "value": business_key[1],
                                "source": str(document),
                                "duplicate_of": business_seen[business_key],
                                "confidence": "high",
                            }
                        )
                        continue
                    if business_key:
                        business_seen[business_key] = str(document)
                    invoices.append(invoice.row())
                    known_invoices.append((invoice, document, item))
                    if invoice.notes:
                        errors.append({"source": str(document), "issue": invoice.notes})
                except Exception as exc:
                    errors.append(
                        {
                            "source": str(document),
                            "issue": f"{type(exc).__name__}: {exc}",
                        }
                    )
        except Exception as exc:
            errors.append(
                {
                    "source": item.filename,
                    "issue": f"{type(exc).__name__}: {exc}",
                }
            )

    for invoice, document, item in unparsed:
        subject_key = normalized_search(item.subject)
        sender_key = normalized_sender(item.sender)
        matches = []
        for known_invoice, known_document, known_item in known_invoices:
            invoice_number = normalized_search(known_invoice.invoice_number)
            if (
                invoice_number
                and invoice_number in subject_key
                and normalized_sender(known_item.sender) == sender_key
            ):
                matches.append((known_invoice, known_document))
        if len(matches) == 1:
            known_invoice, known_document = matches[0]
            duplicates.append(
                {
                    "kind": "subject_invoice_number+sender",
                    "value": known_invoice.invoice_number,
                    "source": str(document),
                    "duplicate_of": str(known_document),
                    "confidence": "medium",
                }
            )
            continue
        errors.append(
            {
                "source": str(document),
                "issue": invoice.notes or "insufficient invoice fields",
            }
        )

    summary = {
        "start_date": str(args.start_date),
        "end_date": str(args.end_date),
        "timezone": args.timezone,
        "messages": message_count,
        "attachments": len(found),
        "attachments_saved": len(attachment_rows),
        "invoices": len(invoices),
        "duplicates": len(duplicates),
        "errors": len(errors),
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    workbook = root / "invoice_report.xlsx"
    write_report(workbook, invoices, attachment_rows, duplicates, errors, summary)
    print(
        json.dumps(
            {
                **summary,
                "dry_run": False,
                "output_dir": str(root),
                "workbook": str(workbook),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            )
        )
        raise SystemExit(1)
