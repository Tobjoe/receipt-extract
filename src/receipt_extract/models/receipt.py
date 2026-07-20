"""Pydantic v2 models for receipts, line items and confidence scores.

All models are frozen (immutable). Use ``model_copy(update=...)`` to derive
modified instances instead of mutating in place.
"""

from __future__ import annotations

from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from receipt_extract.models.currency import ISO_4217

# Tolerances for numeric consistency checks (in currency units / percent).
AMOUNT_TOLERANCE = Decimal("0.05")
VAT_TOLERANCE = Decimal("0.05")


class Confidence(BaseModel):
    """Per-field extraction confidence in the range [0, 1]."""

    model_config = ConfigDict(frozen=True)

    vendor: float | None = Field(default=None, ge=0.0, le=1.0)
    date: float | None = Field(default=None, ge=0.0, le=1.0)
    currency: float | None = Field(default=None, ge=0.0, le=1.0)
    total: float | None = Field(default=None, ge=0.0, le=1.0)
    vat_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    vat_amount: float | None = Field(default=None, ge=0.0, le=1.0)
    payment_method: float | None = Field(default=None, ge=0.0, le=1.0)


class LineItem(BaseModel):
    """A single line on a receipt: amount must equal quantity * unit_price."""

    model_config = ConfigDict(frozen=True)

    description: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    amount: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def _check_amount(self) -> LineItem:
        expected = self.quantity * self.unit_price
        if abs(self.amount - expected) > AMOUNT_TOLERANCE:
            raise ValueError(
                f"amount {self.amount} != quantity*unit_price {expected} "
                f"(tolerance {AMOUNT_TOLERANCE})"
            )
        return self


class Receipt(BaseModel):
    """A validated receipt with line items and optional confidence scores."""

    model_config = ConfigDict(frozen=True)

    vendor: str = Field(min_length=1)
    date: date_type
    currency: str
    total: Decimal = Field(ge=0)
    vat_rate: Decimal | None = Field(default=None, ge=0, le=100)
    vat_amount: Decimal | None = Field(default=None, ge=0)
    line_items: list[LineItem] = Field(default_factory=list)
    payment_method: str | None = None
    confidence: Confidence | None = None

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("currency must be a string")
        code = v.strip().upper()
        if code not in ISO_4217:
            raise ValueError(f"currency {code!r} is not a known ISO-4217 code")
        return code

    @field_validator("date")
    @classmethod
    def _not_in_future(cls, v: date_type) -> date_type:
        if v > date_type.today():
            raise ValueError(f"date {v} is in the future")
        return v

    @model_validator(mode="after")
    def _check_total(self) -> Receipt:
        if self.line_items:
            line_sum = sum((li.amount for li in self.line_items), Decimal("0"))
            if abs(self.total - line_sum) > AMOUNT_TOLERANCE:
                raise ValueError(
                    f"total {self.total} != sum(line_items) {line_sum} "
                    f"(tolerance {AMOUNT_TOLERANCE})"
                )
        return self

    @model_validator(mode="after")
    def _check_vat(self) -> Receipt:
        if self.vat_rate is not None and self.vat_amount is not None:
            # Gross total includes VAT: net = total / (1 + rate/100).
            rate = self.vat_rate / Decimal("100")
            net = self.total / (Decimal("1") + rate)
            expected_vat = net * rate
            if abs(self.vat_amount - expected_vat) > VAT_TOLERANCE:
                raise ValueError(
                    f"vat_amount {self.vat_amount} inconsistent with vat_rate "
                    f"{self.vat_rate}% (expected ~{expected_vat:.2f})"
                )
        return self
