from __future__ import annotations

import re, shutil, subprocess, tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from xml.etree import ElementTree as ET

@dataclass
class Invoice:
    source: str = ""; seller_name: str = ""; seller_tax_id: str = ""; buyer_name: str = ""; buyer_tax_id: str = ""
    symbol: str = ""; invoice_number: str = ""; invoice_date: str = ""; currency: str = ""; subtotal: str = ""; tax: str = ""; total: str = ""; confidence: str = "low"; notes: str = ""
    def row(self): return asdict(self)

def clean(v: str) -> str: return re.sub(r"\s+", " ", v or "").strip()
def local(tag: str) -> str: return tag.rsplit("}", 1)[-1].lower()

def parse_xml(path: Path) -> Invoice:
    raw = path.read_bytes()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper(): raise ValueError("DTD/entity declarations rejected")
    root = ET.fromstring(raw)
    vals: dict[str, list[str]] = {}
    for e in root.iter():
        if e.text and clean(e.text): vals.setdefault(local(e.tag), []).append(clean(e.text))
    def pick(*names):
        for n in names:
            if vals.get(n.lower()): return vals[n.lower()][0]
        return ""
    x = Invoice(str(path), pick("tennbhan", "sellername", "tennban"), pick("mstnbhan", "sellertaxcode", "masothue"), pick("tennmua", "buyername"), pick("mstnmua", "buyertaxcode"), pick("khhdon", "invoiceseries", "symbol"), pick("shdon", "invoiceno", "number"), pick("nlap", "invoicedate", "issuedate"), pick("dvtte", "currency"), pick("tgtcthue", "subtotal"), pick("tgtthue", "taxamount"), pick("tgtttbso", "totalamount", "total"), "high")
    if not x.invoice_number: x.notes = "invoice number missing"
    return x

LABELS = {
 "seller_tax_id":[r"(?:seller\s+tax\s+id|m[aã]\s+s[oố]\s+thu[eế])\s*[:#]?\s*([0-9-]{8,20})"],
 "symbol":[r"(?:k[yý]\s+hi[eệ]u|symbol|series)\s*[:#]?\s*([A-Z0-9/.-]{2,20})"],
 "invoice_number":[r"(?:s[oố]\s+h[oó]a\s+[dđ][oơ]n|invoice\s*(?:no|number))\s*[:#]?\s*([A-Z0-9/-]{1,20})"],
 "invoice_date":[r"(?:ng[aà]y\s+l[aậ]p|invoice\s+date|date)\s*[:#]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})"],
 "total":[r"(?:t[oổ]ng\s+(?:c[oộ]ng\s+)?ti[eề]n\s+thanh\s+to[aá]n|amount\s+due|grand\s+total)\s*[:]?\s*([0-9][0-9., ]*)"]}

def extract_text(path: Path, ocr: bool=False) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
            text = "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)
        except ImportError:
            try:
                import pdfplumber
                with pdfplumber.open(path) as doc: text = "\n".join((p.extract_text() or "") for p in doc.pages)
            except ImportError: text = ""
        if text.strip() or not ocr: return text
    if ocr and ext in {".jpg", ".jpeg", ".png"} and shutil.which("tesseract"):
        r = subprocess.run(["tesseract", str(path), "stdout", "-l", "vie+eng"], capture_output=True, text=True, timeout=120, check=False)
        return r.stdout if r.returncode == 0 else ""
    return ""

def parse_document(path: Path, ocr: bool=False) -> Invoice:
    if path.suffix.lower() == ".xml": return parse_xml(path)
    text = extract_text(path, ocr)
    inv = Invoice(source=str(path), confidence="medium" if text else "low")
    for field, patterns in LABELS.items():
        hits=[]
        for pattern in patterns: hits += re.findall(pattern, text, re.I)
        hits = list(dict.fromkeys(clean(x) for x in hits if clean(x)))
        if len(hits) == 1: setattr(inv, field, hits[0])
        elif len(hits) > 1: inv.notes += f"ambiguous {field}; "
    if not text: inv.notes += "no extractable text; "
    return inv
