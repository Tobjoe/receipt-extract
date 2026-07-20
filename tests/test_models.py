from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from receipt_extract.models import Confidence, LineItem, Receipt


def _line(desc="Coffee", qty="2", price="2.50", amount="5.00"):
    return LineItem(
        description=desc,
        quantity=Decimal(qty),
        unit_price=Decimal(price),
        amount=Decimal(amount),
    )


def _receipt(**overrides):
    base = dict(
        vendor="Cafe Bern",
        date=date(2026, 1, 15),
        currency="CHF",
        total=Decimal("5.00"),
        vat_rate=Decimal("8.1"),
        vat_amount=Decimal("0.37"),
        line_items=[_line()],
        payment_method="card",
    )
    base.update(overrides)
    return Receipt(**base)


class TestLineItem:
    def test_valid_line_item(self):
        item = _line()
        assert item.amount == Decimal("5.00")

    def test_amount_must_match_qty_times_price(self):
        with pytest.raises(ValidationError):
            LineItem(
                description="x",
                quantity=Decimal("2"),
                unit_price=Decimal("2.50"),
                amount=Decimal("9.99"),
            )

    def test_amount_tolerance(self):
        # 2 * 2.50 = 5.00, within 0.05 tolerance
        LineItem(
            description="x",
            quantity=Decimal("2"),
            unit_price=Decimal("2.50"),
            amount=Decimal("5.03"),
        )

    def test_negative_quantity_rejected(self):
        with pytest.raises(ValidationError):
            LineItem(
                description="x",
                quantity=Decimal("-1"),
                unit_price=Decimal("2.50"),
                amount=Decimal("-2.50"),
            )


class TestReceipt:
    def test_valid_receipt(self):
        r = _receipt()
        assert r.currency == "CHF"

    def test_total_must_match_line_items_sum(self):
        with pytest.raises(ValidationError):
            _receipt(total=Decimal("99.00"))

    def test_total_tolerance(self):
        _receipt(total=Decimal("5.04"))

    def test_vat_amount_consistency(self):
        # vat_rate 8.1% on net -> inconsistent vat_amount rejected
        with pytest.raises(ValidationError):
            _receipt(vat_amount=Decimal("2.00"))

    def test_future_date_rejected(self):
        with pytest.raises(ValidationError):
            _receipt(date=date.today() + timedelta(days=2))

    def test_invalid_currency_rejected(self):
        with pytest.raises(ValidationError):
            _receipt(currency="XYZ")

    def test_currency_normalized_uppercase(self):
        r = _receipt(currency="chf")
        assert r.currency == "CHF"

    def test_immutable_model_copy(self):
        r = _receipt()
        r2 = r.model_copy(update={"vendor": "New Vendor"})
        assert r.vendor == "Cafe Bern"
        assert r2.vendor == "New Vendor"

    def test_frozen_cannot_mutate(self):
        r = _receipt()
        with pytest.raises(ValidationError):
            r.vendor = "hack"


class TestConfidence:
    def test_confidence_bounds(self):
        Confidence(vendor=0.9, date=0.8, total=0.99)
        with pytest.raises(ValidationError):
            Confidence(vendor=1.5)

    def test_receipt_with_confidence(self):
        r = _receipt(confidence=Confidence(vendor=0.9, total=0.95))
        assert r.confidence.vendor == 0.9
