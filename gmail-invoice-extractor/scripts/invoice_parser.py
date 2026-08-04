from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


@dataclass
class Invoice:
    source: str = ""
    seller_name: str = ""
    seller_tax_id: str = ""
    buyer_name: str = ""
    buyer_tax_id: str = ""
    symbol: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    payment_method: str = ""
    currency: str = ""
    subtotal: str = ""
    tax_rate: str = ""
    tax: str = ""
    total: str = ""
    confidence: str = "low"
    notes: str = ""

    def row(self) -> dict:
        return asdict(self)

    def is_candidate(self) -> bool:
        if self.invoice_number and (self.seller_tax_id or self.symbol):
            return True
        identifying = [self.seller_tax_id, self.symbol, self.invoice_date, self.total]
        return sum(bool(value.strip()) for value in identifying) >= 3

    def business_key(self) -> tuple[str, str] | None:
        seller_tax_id = self.seller_tax_id.strip().lower()
        symbol = self.symbol.strip().lower()
        invoice_number = self.invoice_number.strip().lower()
        if seller_tax_id and invoice_number:
            return "seller_tax_id+invoice_number", f"{seller_tax_id}|{invoice_number}"
        if symbol and invoice_number:
            return "symbol+invoice_number", f"{symbol}|{invoice_number}"
        return None


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def parse_xml(path: Path) -> Invoice:
    raw = path.read_bytes()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("DTD/entity declarations rejected")
    root = ET.fromstring(raw)
    values: dict[str, list[str]] = {}
    for element in root.iter():
        if element.text and clean(element.text):
            values.setdefault(local(element.tag), []).append(clean(element.text))

    def pick(*names: str) -> str:
        for name in names:
            if values.get(name.lower()):
                return values[name.lower()][0]
        return ""

    invoice = Invoice(
        source=str(path),
        seller_name=pick("tennbhan", "sellername", "tennban"),
        seller_tax_id=pick("mstnbhan", "sellertaxcode", "masothue"),
        buyer_name=pick("tennmua", "buyername"),
        buyer_tax_id=pick("mstnmua", "buyertaxcode"),
        symbol=pick("khhdon", "invoiceseries", "symbol"),
        invoice_number=pick("shdon", "invoiceno", "number"),
        invoice_date=pick("nlap", "invoicedate", "issuedate"),
        payment_method=pick("htttoan", "paymentmethod"),
        currency=pick("dvtte", "currency"),
        subtotal=pick("tgtcthue", "subtotal"),
        tax_rate=pick("tsuat", "taxrate"),
        tax=pick("tgtthue", "taxamount"),
        total=pick("tgtttbso", "totalamount", "total"),
        confidence="high",
    )
    if not invoice.invoice_number:
        invoice.notes = "invoice number missing"
    return invoice


def extract_text(path: Path, ocr: bool = False) -> str:
    extension = path.suffix.lower()
    if extension == ".pdf":
        try:
            from pypdf import PdfReader

            text = "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
        except Exception:
            text = ""
        if not text.strip():
            try:
                import pdfplumber

                with pdfplumber.open(path) as document:
                    text = "\n".join((page.extract_text() or "") for page in document.pages)
            except Exception:
                text = ""
        if text.strip() or not ocr:
            return text
    if ocr and extension in {".jpg", ".jpeg", ".png"} and shutil.which("tesseract"):
        result = subprocess.run(
            ["tesseract", str(path), "stdout", "-l", "vie+eng"],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return result.stdout if result.returncode == 0 else ""
    return ""


def first_match(text: str, pattern: str) -> str:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    return clean(match.group(1)) if match else ""


def amount_after_label(lines: list[str], label_pattern: str) -> str:
    for index, line in enumerate(lines):
        match = re.search(label_pattern, line, re.IGNORECASE)
        if not match:
            continue
        pieces: list[str] = []
        remainder = line[match.end() :].lstrip(" :")
        if re.search(r"\d", remainder):
            pieces.append(remainder)
        for following in lines[index + 1 : index + 4]:
            if re.sub(r"[0-9.,\sđĐ₫]+", "", following):
                break
            if re.search(r"\d", following):
                pieces.append(following)
        amount = "".join(re.findall(r"[0-9.,]+", " ".join(pieces))).strip(".,")
        return amount
    return ""


def seller_name_from_header(lines: list[str]) -> str:
    explicit = first_match(
        " ".join(lines),
        r"(?:Tên\s+người\s+bán|Seller(?:\s+name)?)\s*:\s*(.+?)\s+(?=Địa\s+chỉ|Address|MST|Tax\s+ID)",
    )
    if explicit:
        return explicit
    heading_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.search(r"(?:Hóa\s+đơn|Invoice)", line, re.IGNORECASE)
        ),
        0,
    )
    candidates = []
    for line in lines[:heading_index]:
        if re.search(r"(?:Địa\s+chỉ|Address|MST|Tax\s+ID|Email|SĐT|Phone)", line, re.IGNORECASE):
            break
        candidates.append(line)
    return clean(" ".join(candidates))


def parse_document(path: Path, ocr: bool = False) -> Invoice:
    if path.suffix.lower() == ".xml":
        return parse_xml(path)

    text = extract_text(path, ocr)
    lines = [clean(line) for line in text.splitlines() if clean(line)]
    flattened = " ".join(lines)
    invoice = Invoice(source=str(path))
    if not flattened:
        invoice.notes = "no extractable text"
        return invoice

    invoice.seller_name = seller_name_from_header(lines)
    invoice.seller_tax_id = first_match(
        flattened,
        r"(?:\bMST|Seller\s+Tax\s+ID)\s*[:#]?\s*([0-9-]{8,20})",
    )
    invoice.buyer_name = first_match(
        flattened,
        r"(?:Đơn\s+vị\s+mua\s+hàng|Buyer(?:\s+company|\s+name)?)\s*:\s*(.+?)\s+(?=Người\s+mua\s+hàng|Buyer\s+contact|Địa\s+chỉ|Address|Mã\s+số\s+thuế|Buyer\s+Tax\s+ID)",
    )
    invoice.buyer_tax_id = first_match(
        flattened,
        r"(?:Người\s+mua\s+hàng|Buyer\s+contact)\s*:.*?(?:Mã\s+số\s+thuế|Buyer\s+Tax\s+ID)\s*:\s*([0-9-]{8,20})",
    )
    invoice.invoice_number = first_match(
        flattened,
        r"(?:\bSố(?:\s+hóa\s+đơn)?|Invoice\s*(?:No|Number))\s*[:#]?\s*([A-Z0-9/-]{3,30})",
    )
    invoice.invoice_date = first_match(
        flattened,
        r"(?:Ngày\s+lập|Invoice\s+date|Issued\s+date|Date)\s*[:#]?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{2}-\d{2})",
    )
    invoice.symbol = first_match(
        flattened,
        r"(?:Ký\s+hiệu|Symbol|Series)\s*[:#]?\s*([A-Z0-9/.-]{2,20})",
    )
    invoice.payment_method = first_match(
        flattened,
        r"(?:Hình\s+thức\s+(?:TT|thanh\s+toán)|Payment\s+method)\s*:\s*(.+?)\s+(?=ST\s*T|Tên\s+hàng|Description|Cộng\s+tiền|Subtotal|$)",
    )
    invoice.subtotal = amount_after_label(
        lines,
        r"(?:Cộng\s+tiền\s+hàng|Subtotal)\s*:",
    )
    invoice.tax_rate = first_match(
        flattened,
        r"(?:Thuế\s+suất|Tax\s+rate)[^:()]*\(?\s*([0-9]+(?:[.,][0-9]+)?)\s*%",
    )
    invoice.tax = amount_after_label(
        lines,
        r"(?:Thuế\s+suất|VAT|Tax\s+amount)[^:]*:",
    )
    invoice.total = amount_after_label(
        lines,
        r"(?:Tổng\s+cộng\s+thanh\s+toán|Amount\s+due|Grand\s+total|Total)\s*:",
    )
    invoice.currency = first_match(
        flattened,
        r"(?:Đơn\s+vị\s+tiền\s+tệ|Currency)\s*:\s*([A-Z]{3})",
    )
    if not invoice.currency and re.search(r"(?:\bVND\b|VNĐ|₫|\sđ\b)", flattened, re.IGNORECASE):
        invoice.currency = "VND"

    populated = sum(
        bool(value)
        for value in (
            invoice.seller_name,
            invoice.seller_tax_id,
            invoice.buyer_name,
            invoice.buyer_tax_id,
            invoice.invoice_number,
            invoice.invoice_date,
            invoice.symbol,
            invoice.subtotal,
            invoice.tax,
            invoice.total,
        )
    )
    if invoice.invoice_number and invoice.total and (invoice.seller_tax_id or invoice.symbol):
        invoice.confidence = "high"
    elif populated >= 4:
        invoice.confidence = "medium"
    else:
        invoice.confidence = "low"

    missing = []
    if not invoice.invoice_number:
        missing.append("invoice number missing")
    if not invoice.total:
        missing.append("total missing")
    invoice.notes = "; ".join(missing)
    return invoice
