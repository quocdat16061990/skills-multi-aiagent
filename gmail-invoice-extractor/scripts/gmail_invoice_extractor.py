#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from excel_report import write_report
from gmail_reader import GmailReader, safe_filename
from invoice_parser import parse_document
from safe_archive import extract_zip

def iso(v):
    try: return date.fromisoformat(v)
    except ValueError as e: raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from e

def main() -> int:
    p=argparse.ArgumentParser(description="Read Gmail invoice attachments and build a review workbook")
    p.add_argument("--start-date", required=True, type=iso); p.add_argument("--end-date", required=True, type=iso)
    p.add_argument("--client-json", required=True, type=Path); p.add_argument("--token-json", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path); p.add_argument("--dry-run", action="store_true"); p.add_argument("--ocr", action="store_true")
    p.add_argument("--max-attachment-bytes", type=int, default=25_000_000)
    a=p.parse_args()
    if a.end_date < a.start_date: p.error("--end-date must be on or after --start-date")
    reader=GmailReader(a.client_json, a.token_json)
    found=[]; messages=[]
    for msg in reader.messages(a.start_date, a.end_date):
        messages.append(msg["id"]); found.extend(reader.attachments(msg))
    if a.dry_run:
        print(json.dumps({"dry_run":True,"messages":len(messages),"attachments":len(found),"items":[{"message_id":x.message_id,"filename":x.filename,"size":x.size} for x in found]}, ensure_ascii=False)); return 0
    root=a.output_dir.resolve(); raw=root/"attachments"; unpacked=root/"unzipped"; raw.mkdir(parents=True, exist_ok=True); unpacked.mkdir(parents=True, exist_ok=True)
    invoices=[]; attachment_rows=[]; duplicates=[]; errors=[]; sha_seen={}; business_seen={}
    for n, item in enumerate(found,1):
        try:
            data=reader.download(item,a.max_attachment_bytes); sha=hashlib.sha256(data).hexdigest()
            if sha in sha_seen:
                duplicates.append({"kind":"sha256","value":sha,"source":item.filename,"duplicate_of":sha_seen[sha]}); continue
            sha_seen[sha]=item.filename
            folder=raw/item.message_id; folder.mkdir(parents=True,exist_ok=True); path=folder/f"{n:04d}_{safe_filename(item.filename)}"; path.write_bytes(data)
            attachment_rows.append({**asdict(item),"sha256":sha,"saved_path":str(path)})
            docs=extract_zip(data,unpacked/f"{n:04d}") if path.suffix.lower()==".zip" else [path]
            for doc in docs:
                try:
                    inv=parse_document(doc,a.ocr); row=inv.row(); key=(inv.seller_tax_id.strip(),inv.symbol.strip(),inv.invoice_number.strip())
                    if all(key) and key in business_seen:
                        duplicates.append({"kind":"business_key","value":"|".join(key),"source":str(doc),"duplicate_of":business_seen[key]}); continue
                    if all(key): business_seen[key]=str(doc)
                    invoices.append(row)
                    if inv.notes or not inv.invoice_number: errors.append({"source":str(doc),"issue":inv.notes or "invoice number missing"})
                except Exception as e: errors.append({"source":str(doc),"issue":type(e).__name__+": "+str(e)})
        except Exception as e: errors.append({"source":item.filename,"issue":type(e).__name__+": "+str(e)})
    summary={"start_date":str(a.start_date),"end_date":str(a.end_date),"messages":len(messages),"attachments":len(found),"invoices":len(invoices),"duplicates":len(duplicates),"errors":len(errors),"generated_at_utc":datetime.utcnow().replace(microsecond=0).isoformat()+"Z"}
    workbook=root/"invoice_report.xlsx"; write_report(workbook,invoices,attachment_rows,duplicates,errors,summary)
    print(json.dumps({**summary,"dry_run":False,"output_dir":str(root),"workbook":str(workbook)},ensure_ascii=False)); return 0

if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as e:
        print(json.dumps({"ok":False,"error":type(e).__name__+": "+str(e)},ensure_ascii=False)); raise SystemExit(1)
