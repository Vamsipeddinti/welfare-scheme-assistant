from pathlib import Path
from unittest.mock import patch
import subprocess

from app.documents import _parse_pages, consistency, extract_document

FIXTURES = Path(__file__).resolve().parents[2] / "data" / "synthetic_documents"


def test_identity_content_and_page_evidence():
    result = extract_document(FIXTURES / "asha-identity.pdf", "unrelated-filename.pdf")
    assert result["status"] == "PROCESSED"
    assert result["document_type"] == "identity_proof"
    assert result["fields"] == {"full_name": "Asha Rao", "date_of_birth": "1988-04-12"}
    assert result["evidence"]["date_of_birth"]["page"] == 1
    assert "confidence" not in result


def test_income_mismatch_and_user_correction():
    result = extract_document(FIXTURES / "meera-income-mismatch.pdf", "income.pdf")
    profile = {"full_name": "Meera Shah", "annual_family_income": 150000}
    assert result["status"] == "PROCESSED"
    assert consistency(profile, result["fields"], "income_certificate")[1]["status"] == "MISMATCH"
    corrected = {**result["fields"], "annual_family_income": 150000}
    assert all(item["status"] == "MATCH" for item in consistency(profile, corrected, "income_certificate"))
    assert result["fields"]["annual_family_income"] == 120000  # Original extraction remains separate.


def test_images_scanned_and_bad_documents_are_not_success():
    for filename in ("synthetic-image.png", "scanned-image.pdf"):
        assert extract_document(FIXTURES / filename, filename)["status"] == "NEEDS_OCR"
    for filename in ("encrypted.pdf", "corrupt.pdf", "spoofed.pdf"):
        assert extract_document(FIXTURES / filename, filename)["status"] == "ERROR"


def test_extension_size_path_traversal_and_empty(tmp_path):
    identity = FIXTURES / "asha-identity.pdf"
    assert extract_document(identity, "identity.png")["status"] == "ERROR"
    assert extract_document(identity, "../identity.pdf")["status"] == "ERROR"
    assert extract_document(identity, "..\\identity.pdf")["status"] == "ERROR"
    assert extract_document(identity, "identity.pdf", max_bytes=5)["status"] == "ERROR"
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    assert extract_document(empty, "empty.pdf")["status"] == "ERROR"


def test_timeout_is_honest():
    with patch("app.documents.subprocess.run", side_effect=subprocess.TimeoutExpired("worker", 15)):
        result = extract_document(FIXTURES / "asha-identity.pdf", "file.pdf")
    assert result["status"] == "ERROR"
    assert "time limit" in result["error"]


def test_unknown_formats_missing_and_conflicting_fields():
    assert _parse_pages(["Full Name: Asha Rao"])["status"] == "NEEDS_MANUAL_REVIEW"
    content = "SYNTHETIC DEMONSTRATION DOCUMENT\nDocument Type: identity_proof\nFull Name: Asha Rao\nDate of Birth: 1988-04-12\nDate of Birth: 1989-04-12"
    result = _parse_pages([content])
    assert result["status"] == "NEEDS_MANUAL_REVIEW"
    assert "date_of_birth" not in result["fields"]


def test_normalization_and_unknown_are_distinct():
    checks = consistency({"full_name": " Asha  Rao ", "annual_family_income": 0, "state": "Telangana", "social_category": "OBC"},
                         {"full_name": "asha rao", "annual_family_income": 0, "state": "telangana", "social_category": "obc"})
    assert [c["status"] for c in checks] == ["MATCH", "UNKNOWN", "MATCH", "MATCH", "MATCH"]
    assert consistency({"has_bank_account": False}, {"has_bank_account": False}, "bank_statement")[1]["status"] == "MATCH"


def test_invalid_extracted_values_require_manual_review():
    result = _parse_pages(["SYNTHETIC DEMONSTRATION DOCUMENT\nDocument Type: income_certificate\nFull Name: Test Citizen\nAnnual Family Income: -100"])
    assert result["status"] == "NEEDS_MANUAL_REVIEW"
    assert "annual_family_income" not in result["fields"]
