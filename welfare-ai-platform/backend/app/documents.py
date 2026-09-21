"""Bounded text extraction for synthetic documents; never document authentication."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

MAX_PAGES = 20
MAX_TEXT = 100_000
EXTRACTION_TIMEOUT = 15
DOCUMENT_FIELDS = {
    "identity_proof": ("full_name", "date_of_birth"),
    "birth_certificate": ("full_name", "date_of_birth"),
    "income_certificate": ("full_name", "annual_family_income"),
    "residence_proof": ("full_name", "state"),
    "category_certificate": ("full_name", "social_category"),
    "student_certificate": ("full_name", "student_status"),
    "disability_certificate": ("full_name", "disability_status"),
    "employment_certificate": ("full_name", "employment_status"),
    "bank_statement": ("full_name", "has_bank_account"),
}
LABELS = {
    "full name": "full_name", "date of birth": "date_of_birth",
    "annual family income": "annual_family_income", "state": "state",
    "social category": "social_category", "student status": "student_status",
    "disability status": "disability_status", "employment status": "employment_status",
    "bank account status": "has_bank_account",
}


def _result(status: str, error: str | None = None, **values) -> dict:
    result = {"document_type": "unknown", "status": status, "fields": {},
              "evidence": {}, "method": "content-validation", **values}
    if error:
        result["error"] = error
    return result


def _value(field: str, value):
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip()
    if field == "annual_family_income":
        amount = Decimal(re.sub(r"(?i)INR|Rs\.?|[₹,\s]", "", text))
        if not amount.is_finite() or amount < 0 or amount > 1_000_000_000:
            raise ValueError("Invalid income")
        return float(amount)
    if field == "date_of_birth":
        parsed = date.fromisoformat(text)
        if parsed > date.today() or parsed.year < 1900:
            raise ValueError("Invalid birth date")
        return parsed.isoformat()
    if field in ("student_status", "disability_status", "has_bank_account"):
        normalized = text.casefold()
        if normalized in ("true", "yes"):
            return True
        if normalized in ("false", "no"):
            return False
        raise ValueError("Expected yes/no")
    if len(text) > 200:
        raise ValueError("Field is too long")
    return " ".join(text.split())


def _parse_pages(pages: list[str]) -> dict:
    text = "\n".join(pages)
    if not text.strip():
        return _result("NEEDS_OCR", "No selectable text found; OCR is disabled.", method="pypdf-text")
    # Deliberately limited to clearly labelled synthetic forms, not guessed official formats.
    match = re.search(r"(?im)^Document Type:\s*([a-z_]+)\s*$", text)
    doc_type = match.group(1) if match else "unknown"
    if doc_type not in DOCUMENT_FIELDS or "SYNTHETIC DEMONSTRATION DOCUMENT" not in text:
        return _result("NEEDS_MANUAL_REVIEW", "Text format is not a supported synthetic template.", method="pypdf-text")
    fields, evidence, conflicts = {}, {}, []
    for page_no, page in enumerate(pages, 1):
        for line in page.splitlines():
            if ":" not in line:
                continue
            label, raw = line.split(":", 1)
            field = LABELS.get(label.strip().casefold())
            if not field:
                continue
            try:
                value = _value(field, raw)
            except (ValueError, InvalidOperation):
                conflicts.append(field)
                continue
            if value is None:
                continue
            if field in fields and fields[field] != value:
                conflicts.append(field)
            else:
                fields[field] = value
                evidence[field] = {"page": page_no, "text": line.strip()[:300]}
    for field in conflicts:
        fields.pop(field, None)
        evidence.pop(field, None)
    missing = [field for field in DOCUMENT_FIELDS[doc_type] if field not in fields]
    status = "NEEDS_MANUAL_REVIEW" if missing or conflicts else "PROCESSED"
    return _result(status, "Missing, invalid or conflicting fields require a user correction." if missing or conflicts else None,
                   document_type=doc_type, fields=fields, evidence=evidence, method="pypdf-synthetic-label-parser",
                   notice="Consistency checking only. This document is not authenticated.")


def _worker(path: Path, kind: str) -> dict:
    # On POSIX bound address space too. Windows deployment uses container memory limits.
    if sys.platform != "win32":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    if kind in ("PNG", "JPEG"):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = 25_000_000
        with Image.open(path) as img:
            if img.format != kind or img.width * img.height > 25_000_000:
                return _result("ERROR", "Invalid image format or image dimensions exceed the limit.")
            img.verify()
        return _result("NEEDS_OCR", "Image content is valid; OCR is disabled.", method="pillow-content-validation")
    from pypdf import PdfReader
    reader = PdfReader(str(path), strict=True)
    if reader.is_encrypted:
        return _result("ERROR", "Encrypted PDFs are not supported.")
    if not reader.pages or len(reader.pages) > MAX_PAGES:
        return _result("ERROR", f"PDF must contain 1 to {MAX_PAGES} pages.")
    pages = []
    total = 0
    for page in reader.pages:
        contents = page.get_contents()
        if contents and len(contents.get_data()) > 4_000_000:
            return _result("ERROR", "PDF page content exceeds extraction limits.")
        page_text = page.extract_text() or ""
        total += len(page_text)
        if total > MAX_TEXT:
            return _result("ERROR", "PDF text exceeds extraction limits.")
        pages.append(page_text)
    return _parse_pages(pages)


def extract_document(path: Path, original_filename: str, max_bytes: int = 10_485_760) -> dict:
    """Parse inside a killable child. Caller owns private storage and upload authorization."""
    path = Path(path)
    if not original_filename or "/" in original_filename or "\\" in original_filename or "\x00" in original_filename:
        return _result("ERROR", "Invalid filename.")
    if not path.is_file() or not 0 < path.stat().st_size <= max_bytes:
        return _result("ERROR", "File is empty, missing, or exceeds the upload limit.")
    with path.open("rb") as handle:
        prefix = handle.read(16)
    suffix = Path(original_filename).suffix.casefold()
    kind = "PDF" if prefix.startswith(b"%PDF-") else "PNG" if prefix.startswith(b"\x89PNG\r\n\x1a\n") else "JPEG" if prefix.startswith(b"\xff\xd8\xff") else None
    if kind is None or suffix not in {"PDF": (".pdf",), "PNG": (".png",), "JPEG": (".jpg", ".jpeg")}[kind]:
        return _result("ERROR", "File content and supported extension must agree (PDF, PNG, JPEG).")
    try:
        output = subprocess.run([sys.executable, str(Path(__file__).resolve()), str(path.resolve()), kind],
                                capture_output=True, text=True, timeout=EXTRACTION_TIMEOUT, check=False)
        if output.returncode != 0:
            return _result("ERROR", "Document is corrupt or could not be parsed safely.")
        return json.loads(output.stdout)
    except subprocess.TimeoutExpired:
        return _result("ERROR", "Document processing exceeded the time limit.")
    except (OSError, ValueError):
        return _result("ERROR", "Document processing failed.")


def consistency(profile: dict, fields: dict, document_type: str | None = None) -> list[dict]:
    """Exact normalized comparisons; no fuzzy name or income tolerance."""
    keys = DOCUMENT_FIELDS.get(document_type, ("full_name", "date_of_birth", "annual_family_income", "state", "social_category"))
    checks = []
    for field in keys:
        pv, dv = profile.get(field), fields.get(field)
        try:
            p, d = _value(field, pv), _value(field, dv)
            if isinstance(p, str):
                p = p.casefold()
            if isinstance(d, str):
                d = d.casefold()
            status = "UNKNOWN" if p is None or d is None else "MATCH" if p == d else "MISMATCH"
        except (ValueError, InvalidOperation):
            status = "UNKNOWN"
        checks.append({"field": field, "status": status, "profile_value": pv, "document_value": dv,
                       "reason": "Missing or invalid information" if status == "UNKNOWN" else "Values agree after normalization" if status == "MATCH" else "Profile and document values differ"})
    return checks


if __name__ == "__main__":
    try:
        print(json.dumps(_worker(Path(sys.argv[1]), sys.argv[2])))
    except Exception:
        # Input-controlled parser diagnostics may contain private data; never expose/log them.
        print(json.dumps(_result("ERROR", "Document is corrupt or could not be parsed safely.")))
