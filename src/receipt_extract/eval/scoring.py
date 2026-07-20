"""Per-field precision/recall/F1 scoring for extracted receipts.

A field prediction counts as:
- true positive (tp): truth present, prediction present and matching
- false positive (fp): prediction present but wrong (or truth absent)
- false negative (fn): truth present but prediction absent or wrong

precision = tp / (tp + fp), recall = tp / (tp + fn).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from receipt_extract.models import Receipt

MONEY_FIELDS = {"total", "vat_amount"}
MONEY_TOLERANCE = Decimal("0.05")
SCALAR_FIELDS = ["vendor", "date", "currency", "total", "vat_rate",
                 "vat_amount", "payment_method"]


@dataclass(frozen=True)
class FieldScore:
    field: str
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int


def values_match(field: str, pred, truth) -> bool:
    """Return True if a predicted value matches the ground truth for a field."""
    if pred is None and truth is None:
        return True
    if pred is None or truth is None:
        return False
    if field in MONEY_FIELDS:
        return abs(Decimal(str(pred)) - Decimal(str(truth))) <= MONEY_TOLERANCE
    if field == "vendor":
        return str(pred).strip().lower() == str(truth).strip().lower()
    return str(pred) == str(truth)


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def score_scalar_field(
    field: str, preds: list[Receipt], truths: list[Receipt]
) -> FieldScore:
    """Score one scalar field across aligned prediction/truth receipt lists."""
    tp = fp = fn = 0
    for pred, truth in zip(preds, truths, strict=True):
        p = getattr(pred, field)
        t = getattr(truth, field)
        if t is None and p is None:
            continue
        if values_match(field, p, t):
            tp += 1
        else:
            if p is not None:
                fp += 1
            if t is not None:
                fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    return FieldScore(field, precision, recall, _f1(precision, recall), tp, fp, fn)
