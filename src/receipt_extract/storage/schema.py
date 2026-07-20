"""SQLite schema DDL for the receipt store."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash      TEXT NOT NULL UNIQUE,
    source         TEXT NOT NULL,
    vendor         TEXT NOT NULL,
    date           TEXT NOT NULL,
    currency       TEXT NOT NULL,
    total          TEXT NOT NULL,
    vat_rate       TEXT,
    vat_amount     TEXT,
    payment_method TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS line_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id  INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    quantity    TEXT NOT NULL,
    unit_price  TEXT NOT NULL,
    amount      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS extraction_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id  INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    model       TEXT NOT NULL,
    attempts    INTEGER NOT NULL,
    tokens_in   INTEGER NOT NULL,
    tokens_out  INTEGER NOT NULL,
    latency_ms  INTEGER NOT NULL,
    cost_usd    REAL NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
