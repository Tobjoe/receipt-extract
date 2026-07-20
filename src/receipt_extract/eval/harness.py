"""Offline evaluation harness.

Loads ground-truth and recorded-prediction receipts from a golden directory,
scores every scalar field, and emits an aggregate report. This runs with zero
API calls; live evaluation would swap the recorded predictions for real
:class:`ReceiptExtractor` output (needs ANTHROPIC_API_KEY).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from receipt_extract.eval.scoring import SCALAR_FIELDS, FieldScore, score_scalar_field
from receipt_extract.models import Receipt


@dataclass(frozen=True)
class EvalReport:
    n_receipts: int
    field_scores: list[FieldScore]

    @property
    def macro_f1(self) -> float:
        if not self.field_scores:
            return 0.0
        return sum(s.f1 for s in self.field_scores) / len(self.field_scores)

    def render_table(self) -> str:
        header = f"{'field':<16}{'prec':>8}{'recall':>8}{'f1':>8}{'tp/fp/fn':>12}"
        rows = [header, "-" * len(header)]
        for s in self.field_scores:
            counts = f"{s.tp}/{s.fp}/{s.fn}"
            rows.append(
                f"{s.field:<16}{s.precision:>8.2f}{s.recall:>8.2f}"
                f"{s.f1:>8.2f}{counts:>12}"
            )
        rows.append("-" * len(header))
        rows.append(f"{'MACRO-F1':<16}{'':>8}{'':>8}{self.macro_f1:>8.2f}")
        rows.append(f"receipts evaluated: {self.n_receipts}")
        return "\n".join(rows)

    def to_dict(self) -> dict:
        return {
            "n_receipts": self.n_receipts,
            "macro_f1": round(self.macro_f1, 4),
            "fields": {
                s.field: {
                    "precision": round(s.precision, 4),
                    "recall": round(s.recall, 4),
                    "f1": round(s.f1, 4),
                    "tp": s.tp, "fp": s.fp, "fn": s.fn,
                }
                for s in self.field_scores
            },
        }


def _load(path: Path) -> Receipt:
    return Receipt.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _load_pairs(golden_dir: Path) -> tuple[list[Receipt], list[Receipt]]:
    truths, preds = [], []
    for truth_path in sorted(golden_dir.glob("*.truth.json")):
        pred_path = truth_path.with_name(
            truth_path.name.replace(".truth.json", ".pred.json")
        )
        if not pred_path.exists():
            raise FileNotFoundError(f"missing prediction for {truth_path.name}")
        truths.append(_load(truth_path))
        preds.append(_load(pred_path))
    return preds, truths


def evaluate(preds: list[Receipt], truths: list[Receipt]) -> EvalReport:
    scores = [score_scalar_field(f, preds, truths) for f in SCALAR_FIELDS]
    return EvalReport(n_receipts=len(truths), field_scores=scores)


def run_offline_eval(golden_dir: Path, out_path: Path) -> EvalReport:
    """Evaluate the golden dataset, write JSON report, return the report."""
    golden_dir = Path(golden_dir)
    if not golden_dir.exists():
        raise FileNotFoundError(f"golden dir not found: {golden_dir}")
    preds, truths = _load_pairs(golden_dir)
    if not truths:
        raise ValueError(f"no *.truth.json found in {golden_dir}")
    report = evaluate(preds, truths)
    Path(out_path).write_text(json.dumps(report.to_dict(), indent=2), "utf-8")
    return report
