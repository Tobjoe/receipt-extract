"""Offline evaluation: golden data generation and per-field metrics."""

from receipt_extract.eval.harness import EvalReport, evaluate, run_offline_eval
from receipt_extract.eval.scoring import FieldScore, score_scalar_field

__all__ = [
    "EvalReport",
    "FieldScore",
    "evaluate",
    "run_offline_eval",
    "score_scalar_field",
]
