"""Printed facts, protocol evidence and exact arithmetic observations."""

from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from enum import Enum
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AMOUNT = re.compile(r"^-?[0-9]+(?:\.[0-9]+)?$")
FieldName = Literal["document_type", "vendor_name", "document_number", "issue_date", "currency", "subtotal", "tax", "total"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentType(str, Enum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    UNKNOWN = "unknown"


class ExtractedFields(Contract):
    document_type: DocumentType
    vendor_name: str | None = Field(max_length=300, description="Vendor name supported by the document")
    document_number: str | None = Field(max_length=100, description="Printed invoice/receipt number, null if absent")
    issue_date: str | None = Field(description="ISO YYYY-MM-DD date when supported and legible, else null")
    currency: str | None = Field(description="ISO currency code when supported by the document, else null")
    subtotal: str | None = Field(max_length=128, description="Plain decimal string without grouping or symbols, else null")
    tax: str | None = Field(max_length=128, description="Plain decimal string without grouping or symbols, else null")
    total: str | None = Field(max_length=128, description="Plain decimal string without grouping or symbols, else null")
    uncertain_fields: list[FieldName] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("vendor_name", "document_number", "notes")
    @classmethod
    def nonblank(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Use null for absent fields, not whitespace")
        return value

    @field_validator("issue_date")
    @classmethod
    def valid_date(cls, value):
        if value is not None:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError("Date must be ISO YYYY-MM-DD or null")
            date.fromisoformat(value)
        return value

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value):
        if value is not None and not re.fullmatch(r"[A-Z]{3}", value):
            raise ValueError("Currency must be a three-letter code or null")
        return value

    @field_validator("subtotal", "tax", "total")
    @classmethod
    def plain_decimal(cls, value):
        if value is not None and not AMOUNT.fullmatch(value):
            raise ValueError("Amount must be a plain decimal string or null; do not guess grouping/locale")
        return value


class ArithmeticStatus(str, Enum):
    MATCHES = "matches"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"


class DatasetSelection(Contract):
    dataset_id: str
    version: str
    profile: str
    case_id: str
    source_sha256: str


class InteractionObservation(Contract):
    interaction_id: str | None = None
    response_model: str | None = None
    status: str | None = None
    reported_usage: dict[str, Any] | None = None
    usage_complete: bool = False
    diagnostic_error_count: int = 0
    cost_usd: None = None


class ExtractionResult(Contract):
    source_name: str
    source_sha256: str
    prompt_sha256: str
    model: str
    fields: ExtractedFields
    raw_output: str
    arithmetic_status: ArithmeticStatus
    computed_total: str | None
    needs_review: bool
    review_reasons: list[str]
    usage: dict | None = None
    observation: InteractionObservation
    dataset: DatasetSelection | None = None


def _decimal(value: str | None) -> Decimal | None:
    if value is None or len(value) > 128 or not AMOUNT.fullmatch(value):
        return None
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    return amount if amount.is_finite() else None


def check_arithmetic(fields: ExtractedFields) -> tuple[ArithmeticStatus, str | None]:
    subtotal, tax, total = (_decimal(fields.subtotal), _decimal(fields.tax), _decimal(fields.total))
    if subtotal is None or tax is None or total is None:
        return ArithmeticStatus.UNKNOWN, None
    # Align all printed digits without assuming a two-decimal currency or relying
    # on the process's default Decimal precision.
    operands = (subtotal, tax)
    exponents = [amount.as_tuple().exponent for amount in operands]
    with localcontext() as context:
        context.prec = max(28, *(len(amount.as_tuple().digits) for amount in operands)) + max(exponents) - min(exponents) + 3
        computed = subtotal + tax
    status = ArithmeticStatus.MATCHES if computed == total else ArithmeticStatus.MISMATCH
    return status, format(computed, "f")


def review_reasons(fields: ExtractedFields, arithmetic: ArithmeticStatus) -> list[str]:
    reasons = [f"missing:{name}" for name in ("vendor_name", "document_number", "issue_date", "currency", "subtotal", "tax", "total")
               if getattr(fields, name) is None]
    if fields.document_type is DocumentType.UNKNOWN:
        reasons.append("unknown_document_type")
    if fields.uncertain_fields:
        reasons.append("uncertain_fields")
    if fields.notes:
        reasons.append("model_notes")
    if arithmetic is ArithmeticStatus.MISMATCH:
        reasons.append("printed_arithmetic_mismatch")
    return reasons
