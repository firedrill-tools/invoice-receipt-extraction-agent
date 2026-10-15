import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from document_extractor.extract import extract_document, load_pdf
from document_extractor.models import ArithmeticStatus, ExtractedFields, check_arithmetic


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ROOT / "data" / "documents"


def test_fixture_pdfs_have_valid_headers() -> None:
    files = sorted(DOCUMENTS.glob("*.pdf"))
    assert len(files) == 3
    for path in files:
        assert len(load_pdf(path)) > 1000


def test_non_pdf_is_rejected_before_provider_call(tmp_path: Path) -> None:
    path = tmp_path / "fake.pdf"
    path.write_text("not a PDF")
    with pytest.raises(ValueError, match="not a PDF"):
        load_pdf(path)


def test_arithmetic_flags_printed_mismatch_without_rewriting_extraction() -> None:
    fields = ExtractedFields(
        document_type="invoice", vendor_name="Cedar Studio", document_number="CS-778",
        issue_date="2026-10-03", currency="USD", subtotal="125.00", tax="10.00",
        total="130.00", uncertain_fields=[], notes=None,
    )
    assert check_arithmetic(fields) == (ArithmeticStatus.MISMATCH, "135.00")
    assert fields.total == "130.00"


def test_absent_money_does_not_become_zero() -> None:
    fields = ExtractedFields(
        document_type="receipt", vendor_name="Birch Market", document_number=None,
        issue_date="2026-10-05", currency="USD", subtotal=None, tax="0.00",
        total="9.50", uncertain_fields=["subtotal"], notes=None,
    )
    assert check_arithmetic(fields) == (ArithmeticStatus.UNKNOWN, None)


def test_inline_pdf_and_schema_are_sent_to_gemini_boundary() -> None:
    expected = {
        "document_type": "invoice", "vendor_name": "Harbor Supplies",
        "document_number": "INV-2041", "issue_date": "2026-10-01", "currency": "CAD",
        "subtotal": "180.00", "tax": "23.40", "total": "203.40",
        "uncertain_fields": [], "notes": None,
    }

    def create(**kwargs: object) -> SimpleNamespace:
        assert kwargs["model"] == "gemini-3.8-flash"
        input_parts = kwargs["input"]
        assert isinstance(input_parts, list)
        assert base64.b64decode(input_parts[0]["data"]).startswith(b"%PDF-")
        assert kwargs["response_format"]["mime_type"] == "application/json"
        return SimpleNamespace(output_text=json.dumps(expected), usage_metadata=None)

    client = SimpleNamespace(interactions=SimpleNamespace(create=create))
    outcome = extract_document(DOCUMENTS / "ordinary-invoice.pdf", model="gemini-3.8-flash", client=client)
    assert outcome.fields.vendor_name == "Harbor Supplies"
    assert outcome.arithmetic_status is ArithmeticStatus.MATCHES
    assert outcome.computed_total == "203.40"
