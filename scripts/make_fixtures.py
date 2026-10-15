"""Rebuild the three fictional PDF fixtures. Requires reportlab, not the app runtime."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "documents"


def make_document(name: str, title: str, vendor: str, rows: list[tuple[str, str]], note: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUT / name), pagesize=letter, invariant=1)
    width, height = letter
    pdf.setFillColor(colors.HexColor("#122235"))
    pdf.rect(0, height - 118, width, 118, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(48, height - 66, title)
    pdf.setFont("Helvetica", 10)
    pdf.drawRightString(width - 48, height - 64, "FICTIONAL SAMPLE DOCUMENT")

    pdf.setFillColor(colors.HexColor("#122235"))
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(48, height - 162, vendor)
    pdf.setFont("Helvetica", 10)
    pdf.setFillColor(colors.HexColor("#536477"))
    pdf.drawString(48, height - 181, "Synthetic records for an agent extraction example")

    y = height - 225
    for label, value in rows:
        pdf.setStrokeColor(colors.HexColor("#D9E0E7"))
        pdf.line(48, y - 8, width - 48, y - 8)
        pdf.setFillColor(colors.HexColor("#536477"))
        pdf.setFont("Helvetica", 10)
        pdf.drawString(48, y + 9, label.upper())
        pdf.setFillColor(colors.HexColor("#122235"))
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawRightString(width - 48, y + 8, value)
        y -= 47

    pdf.setFillColor(colors.HexColor("#F1F5F8"))
    pdf.roundRect(48, y - 18, width - 96, 58, 8, fill=1, stroke=0)
    pdf.setFillColor(colors.HexColor("#122235"))
    pdf.setFont("Helvetica", 10)
    pdf.drawString(62, y + 15, note)
    pdf.setFillColor(colors.HexColor("#667788"))
    pdf.setFont("Helvetica", 9)
    pdf.drawString(48, 48, "Northstar example portfolio - fictional data only")
    pdf.drawRightString(width - 48, 48, "1 / 1")
    pdf.showPage()
    pdf.save()


make_document(
    "ordinary-invoice.pdf",
    "INVOICE",
    "Harbor Supplies",
    [
        ("Invoice number", "INV-2041"),
        ("Issue date", "2026-10-01"),
        ("Services", "Office materials  |  CAD 180.00"),
        ("Subtotal", "CAD 180.00"),
        ("Tax", "CAD 23.40"),
        ("Total due", "CAD 203.40"),
    ],
    "Payment terms: due within 30 days.",
)

make_document(
    "inconsistent-total.pdf",
    "INVOICE",
    "Cedar Studio",
    [
        ("Invoice number", "CS-778"),
        ("Issue date", "2026-10-03"),
        ("Design session", "USD 125.00"),
        ("Subtotal", "USD 125.00"),
        ("Tax", "USD 10.00"),
        ("Printed total", "USD 130.00"),
    ],
    "Amounts are shown exactly as printed; verify before payment.",
)

make_document(
    "partial-receipt.pdf",
    "RECEIPT",
    "Birch Market",
    [
        ("Receipt number", "[unreadable on source copy]"),
        ("Purchase date", "2026-10-05"),
        ("Notebook", "USD 9.50"),
        ("Subtotal", "USD 9.50"),
        ("Tax", "USD 0.00"),
        ("Total paid", "USD 9.50"),
    ],
    "The receipt identifier is not legible in this copy.",
)
