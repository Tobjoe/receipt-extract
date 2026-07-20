from datetime import date
from decimal import Decimal

from receipt_extract.models import LineItem, Receipt
from receipt_extract.pipeline import file_hash, merge_qr_bill
from receipt_extract.qrbill import QRBill


def _receipt(**over):
    base = dict(
        vendor="LLM Vendor",
        date=date(2026, 1, 15),
        currency="EUR",
        total=Decimal("40.00"),
        line_items=[
            LineItem(
                description="x",
                quantity=Decimal("1"),
                unit_price=Decimal("40.00"),
                amount=Decimal("40.00"),
            )
        ],
    )
    base.update(over)
    return Receipt(**base)


def _qr(amount="50.00", currency="CHF"):
    return QRBill(
        iban="CH4431999123000889012",
        amount=Decimal(amount) if amount else None,
        currency=currency,
        creditor="Robert Schneider AG",
        reference_type="QRR",
        reference="210000000003139471430009017",
    )


class TestMerge:
    def test_qr_fields_win_on_conflict(self):
        merged = merge_qr_bill(_receipt(), _qr())
        assert merged.vendor == "Robert Schneider AG"
        assert merged.currency == "CHF"
        assert merged.total == Decimal("50.00")

    def test_conflicting_total_drops_line_items(self):
        # QR total 50 conflicts with line-item sum 40 -> line items dropped
        # to keep the receipt internally consistent.
        merged = merge_qr_bill(_receipt(), _qr())
        assert merged.line_items == []

    def test_matching_total_preserves_line_items(self):
        merged = merge_qr_bill(_receipt(), _qr(amount="40.00"))
        assert len(merged.line_items) == 1
        assert merged.total == Decimal("40.00")

    def test_merge_returns_new_instance(self):
        original = _receipt()
        merged = merge_qr_bill(original, _qr())
        assert original.vendor == "LLM Vendor"
        assert merged is not original

    def test_qr_without_amount_keeps_llm_total(self):
        merged = merge_qr_bill(_receipt(), _qr(amount=""))
        assert merged.total == Decimal("40.00")
        assert len(merged.line_items) == 1


class TestFileHash:
    def test_hash_stable(self, tmp_path):
        f = tmp_path / "a.png"
        f.write_bytes(b"hello")
        assert file_hash(f) == file_hash(f)

    def test_hash_differs_by_content(self, tmp_path):
        a = tmp_path / "a.png"
        b = tmp_path / "b.png"
        a.write_bytes(b"aaa")
        b.write_bytes(b"bbb")
        assert file_hash(a) != file_hash(b)
