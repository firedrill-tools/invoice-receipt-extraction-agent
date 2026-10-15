"""Typed extraction and application-owned arithmetic observations."""

from decimal import Decimal, InvalidOperation
from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    UNKNOWN = "unknown"


class ExtractedFields(BaseModel):
    document_type: DocumentType
    vendor_name: str | None = Field(description="Vendor name exactly as supported by the document")
    document_number: str | None = Field(description="Printed invoice or receipt number, null if absent")
    issue_date: str | None = Field(description="ISO YYYY-MM-DD date when legible, else null")
    currency: str | None = Field(description="ISO 4217 code if supported by the document, else null")
    subtotal: str | None = Field(description="Decimal amount without currency symbol, else null")
    tax: str | None = Field(description="Decimal amount without currency symbol, else null")
    total: str | None = Field(description="Decimal amount without currency symbol, else null")
    uncertain_fields: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, description="Short explanation of legibility or conflicts")


class ArithmeticStatus(str, Enum):
    MATCHES = "matches"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class ExtractionResult(BaseModel):
    source_name: str
    model: str
    fields: ExtractedFields
    arithmetic_status: ArithmeticStatus
    computed_total: str | None
    usage: dict | None = None


def _decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(value.replace(",", ""))
    except InvalidOperation:
        return None
    return amount if amount.is_finite() else None


def check_arithmetic(fields: ExtractedFields) -> tuple[ArithmeticStatus, str | None]:
    subtotal, tax, total = (_decimal(fields.subtotal), _decimal(fields.tax), _decimal(fields.total))
    if subtotal is None or tax is None or total is None:
        return ArithmeticStatus.UNKNOWN, None
    computed = subtotal + tax
    status = ArithmeticStatus.MATCHES if computed == total else ArithmeticStatus.MISMATCH
    return status, f"{computed:.2f}"
