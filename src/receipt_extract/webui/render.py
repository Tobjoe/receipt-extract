"""Pure rendering and loading helpers for the web UI (no Gradio import).

Everything here operates on plain dicts / paths so it can be unit-tested
without a browser, a Gradio install, or an API key.
"""

from __future__ import annotations

import json
from pathlib import Path

from receipt_extract.eval.scoring import SCALAR_FIELDS

__all__ = [
    "SCALAR_FIELDS",
    "diff_rows",
    "eval_report_md",
    "line_item_rows",
    "list_golden_stems",
    "load_receipt_dict",
    "receipt_summary_md",
]


def list_golden_stems(golden_dir: str | Path) -> list[str]:
    """Return sorted sample stems (``easy_1`` ...) that have a truth file."""
    golden = Path(golden_dir)
    stems = [p.name[: -len(".truth.json")] for p in golden.glob("*.truth.json")]
    return sorted(stems)


def load_receipt_dict(path: str | Path) -> dict:
    """Load a receipt JSON file into a plain dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def receipt_summary_md(data: dict) -> str:
    """Render the scalar fields of a receipt dict as a Markdown table."""
    rows = ["| Field | Value |", "| --- | --- |"]
    for field in SCALAR_FIELDS:
        value = data.get(field)
        rows.append(f"| {field} | {'—' if value is None else value} |")
    return "\n".join(rows)


def line_item_rows(data: dict) -> list[list]:
    """Return line items as ``[description, quantity, unit_price, amount]`` rows."""
    rows: list[list] = []
    for item in data.get("line_items") or []:
        rows.append(
            [
                item.get("description", ""),
                item.get("quantity", ""),
                item.get("unit_price", ""),
                item.get("amount", ""),
            ]
        )
    return rows


def diff_rows(pred: dict, truth: dict) -> list[list]:
    """Compare predicted vs ground-truth scalar fields field by field.

    Returns ``[field, predicted, truth, "✓"/"✗"]`` rows. Values are compared as
    strings so ``"12.50"`` and ``12.5`` are treated by their recorded form.
    """
    rows: list[list] = []
    for field in SCALAR_FIELDS:
        p = pred.get(field)
        t = truth.get(field)
        match = "✓" if str(p) == str(t) else "✗"
        rows.append(
            [field, "—" if p is None else str(p), "—" if t is None else str(t), match]
        )
    return rows


def eval_report_md(report: dict) -> str:
    """Render an :meth:`EvalReport.to_dict` payload as a Markdown scorecard."""
    lines = [
        f"**Macro F1: {report['macro_f1']:.3f}**  ·  receipts evaluated: "
        f"{report['n_receipts']}",
        "",
        "| Field | Precision | Recall | F1 | tp / fp / fn |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for field, s in report["fields"].items():
        lines.append(
            f"| {field} | {s['precision']:.2f} | {s['recall']:.2f} | "
            f"{s['f1']:.2f} | {s['tp']} / {s['fp']} / {s['fn']} |"
        )
    return "\n".join(lines)
