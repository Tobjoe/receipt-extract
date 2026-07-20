from datetime import date
from decimal import Decimal

from receipt_extract.extraction.extractor import ExtractionRun
from receipt_extract.models import LineItem, Receipt
from receipt_extract.storage import ReceiptStore


def _receipt():
    return Receipt(
        vendor="Cafe Bern",
        date=date(2026, 1, 15),
        currency="CHF",
        total=Decimal("5.00"),
        line_items=[
            LineItem(
                description="Coffee",
                quantity=Decimal("2"),
                unit_price=Decimal("2.50"),
                amount=Decimal("5.00"),
            )
        ],
    )


def _run():
    return ExtractionRun(
        model="claude-x", attempts=1, tokens_in=100, tokens_out=50, latency_ms=87
    )


def test_save_and_retrieve(tmp_path):
    store = ReceiptStore(tmp_path / "r.db")
    store.save(_receipt(), _run(), file_hash="abc123", source="r.png", cost_usd=0.002)
    got = store.get_by_hash("abc123")
    assert got is not None
    assert got.vendor == "Cafe Bern"
    assert len(got.line_items) == 1
    assert got.line_items[0].description == "Coffee"
    store.close()


def test_idempotent_by_hash(tmp_path):
    store = ReceiptStore(tmp_path / "r.db")
    first = store.save(_receipt(), _run(), file_hash="dup", source="r.png", cost_usd=0.0)
    second = store.save(_receipt(), _run(), file_hash="dup", source="r.png", cost_usd=0.0)
    assert first == second  # same receipt id, no duplicate row
    assert store.count_receipts() == 1
    store.close()


def test_exists(tmp_path):
    store = ReceiptStore(tmp_path / "r.db")
    assert not store.exists("nope")
    store.save(_receipt(), _run(), file_hash="h1", source="r.png", cost_usd=0.0)
    assert store.exists("h1")
    store.close()


def test_extraction_run_persisted(tmp_path):
    store = ReceiptStore(tmp_path / "r.db")
    store.save(_receipt(), _run(), file_hash="h2", source="r.png", cost_usd=0.005)
    run = store.get_run_by_hash("h2")
    assert run["model"] == "claude-x"
    assert run["tokens_in"] == 100
    assert run["cost_usd"] == 0.005
    store.close()


def test_get_missing_returns_none(tmp_path):
    store = ReceiptStore(tmp_path / "r.db")
    assert store.get_by_hash("missing") is None
    store.close()
