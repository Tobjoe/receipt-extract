"""End-to-end ingestion pipeline: detect QR-bill, extract, merge, store.

The QR-bill (when present) is the authoritative source for payment fields, so
its values win on conflict with the LLM extraction. QR payloads are read from a
deterministic ``<file>.spc`` sidecar to keep the pipeline offline-testable;
decoding a QR code from pixels is out of scope (see README Limitations).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from receipt_extract.extraction.extractor import ExtractionResult, ReceiptExtractor
from receipt_extract.models import Receipt
from receipt_extract.models.receipt import AMOUNT_TOLERANCE
from receipt_extract.qrbill import QRBill, parse_qr_bill
from receipt_extract.storage import ReceiptStore

_HASH_CHUNK = 65536


def file_hash(path: Path) -> str:
    """Return a stable SHA-256 hex digest of the file contents."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while chunk := fh.read(_HASH_CHUNK):
            digest.update(chunk)
    return digest.hexdigest()


def load_qr_sidecar(path: Path) -> QRBill | None:
    """Parse ``<path>.spc`` if it exists, else return None."""
    sidecar = Path(str(path) + ".spc")
    if not sidecar.exists():
        return None
    return parse_qr_bill(sidecar.read_text(encoding="utf-8"))


def merge_qr_bill(receipt: Receipt, qr: QRBill) -> Receipt:
    """Return a new Receipt with QR-bill fields taking precedence.

    If the QR total conflicts with the line-item sum, line items are dropped to
    keep the receipt internally consistent (the QR amount is authoritative).
    """
    updates: dict = {"vendor": qr.creditor, "currency": qr.currency}
    if qr.amount is not None:
        updates["total"] = qr.amount
        line_sum = sum((li.amount for li in receipt.line_items), Decimal("0"))
        if abs(qr.amount - line_sum) > AMOUNT_TOLERANCE:
            updates["line_items"] = []
    return receipt.model_copy(update=updates)


@dataclass(frozen=True)
class IngestResult:
    receipt_id: int
    receipt: Receipt
    was_cached: bool


def ingest(
    path: Path,
    extractor: ReceiptExtractor,
    store: ReceiptStore,
    *,
    cost_usd: float = 0.0,
) -> IngestResult:
    """Ingest one receipt file idempotently and return the stored result."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"input file not found: {path}")

    digest = file_hash(path)
    if store.exists(digest):
        cached = store.get_by_hash(digest)
        run_row = store.get_run_by_hash(digest)
        return IngestResult(run_row["receipt_id"], cached, was_cached=True)

    result: ExtractionResult = extractor.extract(path)
    receipt = result.receipt
    qr = load_qr_sidecar(path)
    if qr is not None:
        receipt = merge_qr_bill(receipt, qr)

    receipt_id = store.save(
        receipt, result.run, file_hash=digest, source=str(path), cost_usd=cost_usd
    )
    return IngestResult(receipt_id, receipt, was_cached=False)
