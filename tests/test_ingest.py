from datetime import date
from decimal import Decimal

from receipt_extract.extraction.extractor import ExtractionResult, ExtractionRun
from receipt_extract.models import LineItem, Receipt
from receipt_extract.pipeline import ingest
from receipt_extract.storage import ReceiptStore


class FakeExtractor:
    def __init__(self, receipt):
        self._receipt = receipt
        self.calls = 0

    def extract(self, path):
        self.calls += 1
        run = ExtractionRun(model="stub", attempts=1, tokens_in=10,
                            tokens_out=5, latency_ms=1)
        return ExtractionResult(receipt=self._receipt, run=run)


def _receipt(vendor="LLM Vendor", currency="EUR", total="40.00"):
    return Receipt(
        vendor=vendor, date=date(2026, 1, 15), currency=currency,
        total=Decimal(total),
        line_items=[LineItem(description="x", quantity=Decimal("1"),
                             unit_price=Decimal(total), amount=Decimal(total))],
    )


def test_ingest_stores_receipt(tmp_path):
    img = tmp_path / "r.png"
    img.write_bytes(b"fake-image")
    store = ReceiptStore(tmp_path / "db.sqlite")
    result = ingest(img, FakeExtractor(_receipt()), store)
    assert not result.was_cached
    assert store.count_receipts() == 1
    store.close()


def test_ingest_is_idempotent(tmp_path):
    img = tmp_path / "r.png"
    img.write_bytes(b"fake-image")
    store = ReceiptStore(tmp_path / "db.sqlite")
    extractor = FakeExtractor(_receipt())
    first = ingest(img, extractor, store)
    second = ingest(img, extractor, store)
    assert extractor.calls == 1  # cached, not re-extracted
    assert first.receipt_id == second.receipt_id
    assert second.was_cached
    store.close()


def test_ingest_merges_qr_sidecar(tmp_path):
    img = tmp_path / "r.png"
    img.write_bytes(b"fake-image")
    sidecar = tmp_path / "r.png.spc"
    payload = "\r\n".join([
        "SPC", "0200", "1", "CH4431999123000889012",
        "S", "QR Creditor AG", "Street", "1", "2501", "Biel", "CH",
        "", "", "", "", "", "", "",
        "40.00", "CHF",
        "S", "Debtor", "St", "1", "9400", "Rorschach", "CH",
        "QRR", "210000000003139471430009017", "", "EPD",
    ])
    sidecar.write_text(payload, encoding="utf-8")
    store = ReceiptStore(tmp_path / "db.sqlite")
    result = ingest(img, FakeExtractor(_receipt()), store)
    assert result.receipt.vendor == "QR Creditor AG"  # QR wins
    assert result.receipt.currency == "CHF"
    store.close()


def test_ingest_missing_file_raises(tmp_path):
    store = ReceiptStore(tmp_path / "db.sqlite")
    try:
        ingest(tmp_path / "nope.png", FakeExtractor(_receipt()), store)
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass
    finally:
        store.close()
