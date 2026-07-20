"""Repository-pattern access to the SQLite receipt store.

Monetary values are stored as text to preserve Decimal precision exactly.
Writes are idempotent on ``file_hash``: re-saving the same source file returns
the existing receipt id instead of inserting a duplicate.
"""

from __future__ import annotations

import sqlite3
from datetime import date as date_type
from decimal import Decimal
from pathlib import Path

from receipt_extract.extraction.extractor import ExtractionRun
from receipt_extract.models import Confidence, LineItem, Receipt
from receipt_extract.storage.schema import SCHEMA


class ReceiptStore:
    """CRUD access for receipts, line items and extraction runs."""

    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def exists(self, file_hash: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM receipts WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        return row is not None

    def count_receipts(self) -> int:
        return self._conn.execute("SELECT COUNT(*) AS n FROM receipts").fetchone()["n"]

    def save(
        self,
        receipt: Receipt,
        run: ExtractionRun,
        *,
        file_hash: str,
        source: str,
        cost_usd: float,
    ) -> int:
        """Persist a receipt idempotently; return its id."""
        existing = self._conn.execute(
            "SELECT id FROM receipts WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        if existing is not None:
            return existing["id"]

        cur = self._conn.execute(
            """INSERT INTO receipts
               (file_hash, source, vendor, date, currency, total,
                vat_rate, vat_amount, payment_method)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                file_hash, source, receipt.vendor, receipt.date.isoformat(),
                receipt.currency, str(receipt.total),
                None if receipt.vat_rate is None else str(receipt.vat_rate),
                None if receipt.vat_amount is None else str(receipt.vat_amount),
                receipt.payment_method,
            ),
        )
        receipt_id = cur.lastrowid
        self._insert_line_items(receipt_id, receipt.line_items)
        self._insert_run(receipt_id, run, cost_usd)
        self._conn.commit()
        return receipt_id

    def _insert_line_items(self, receipt_id: int, items: list[LineItem]) -> None:
        self._conn.executemany(
            """INSERT INTO line_items
               (receipt_id, description, quantity, unit_price, amount)
               VALUES (?, ?, ?, ?, ?)""",
            [
                (receipt_id, li.description, str(li.quantity),
                 str(li.unit_price), str(li.amount))
                for li in items
            ],
        )

    def _insert_run(self, receipt_id: int, run: ExtractionRun, cost_usd: float) -> None:
        self._conn.execute(
            """INSERT INTO extraction_runs
               (receipt_id, model, attempts, tokens_in, tokens_out,
                latency_ms, cost_usd)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (receipt_id, run.model, run.attempts, run.tokens_in,
             run.tokens_out, run.latency_ms, cost_usd),
        )

    def get_by_hash(self, file_hash: str) -> Receipt | None:
        row = self._conn.execute(
            "SELECT * FROM receipts WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        if row is None:
            return None
        items = self._conn.execute(
            "SELECT * FROM line_items WHERE receipt_id = ? ORDER BY id", (row["id"],)
        ).fetchall()
        return _row_to_receipt(row, items)

    def get_run_by_hash(self, file_hash: str) -> dict | None:
        row = self._conn.execute(
            """SELECT r.* FROM extraction_runs r
               JOIN receipts rc ON rc.id = r.receipt_id
               WHERE rc.file_hash = ?""",
            (file_hash,),
        ).fetchone()
        return dict(row) if row is not None else None


def _row_to_receipt(row: sqlite3.Row, item_rows: list[sqlite3.Row]) -> Receipt:
    line_items = [
        LineItem(
            description=r["description"],
            quantity=Decimal(r["quantity"]),
            unit_price=Decimal(r["unit_price"]),
            amount=Decimal(r["amount"]),
        )
        for r in item_rows
    ]
    return Receipt(
        vendor=row["vendor"],
        date=date_type.fromisoformat(row["date"]),
        currency=row["currency"],
        total=Decimal(row["total"]),
        vat_rate=None if row["vat_rate"] is None else Decimal(row["vat_rate"]),
        vat_amount=None if row["vat_amount"] is None else Decimal(row["vat_amount"]),
        line_items=line_items,
        payment_method=row["payment_method"],
        confidence=Confidence(),
    )
