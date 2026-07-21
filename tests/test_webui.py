"""Unit tests for the web-UI render helpers (no Gradio, no API key needed)."""

from pathlib import Path

from receipt_extract.eval import run_offline_eval
from receipt_extract.webui.render import (
    diff_rows,
    eval_report_md,
    line_item_rows,
    list_golden_stems,
    load_receipt_dict,
    receipt_summary_md,
)

GOLDEN = Path("data/golden")


def test_list_golden_stems_returns_sorted_sample_names():
    stems = list_golden_stems(GOLDEN)
    assert "easy_1" in stems
    assert stems == sorted(stems)
    assert all(".truth" not in s for s in stems)


def test_receipt_summary_md_renders_all_scalar_fields():
    data = load_receipt_dict(GOLDEN / "easy_1.pred.json")
    md = receipt_summary_md(data)
    assert "| vendor | Cafe Bern |" in md
    assert "| total | 12.50 |" in md
    # None fields render as an em dash, not the literal "None".
    assert "| vat_rate | — |" in md
    assert "None" not in md


def test_line_item_rows_maps_all_columns():
    data = load_receipt_dict(GOLDEN / "easy_1.pred.json")
    rows = line_item_rows(data)
    assert rows[0] == ["Coffee", "2", "2.50", "5.00"]
    assert len(rows) == 2


def test_line_item_rows_handles_missing_line_items():
    assert line_item_rows({"line_items": None}) == []
    assert line_item_rows({}) == []


def test_diff_rows_flags_matches_and_mismatches():
    pred = {"vendor": "A", "total": "10.00", "vat_rate": None}
    truth = {"vendor": "A", "total": "11.00", "vat_rate": None}
    rows = {r[0]: r for r in diff_rows(pred, truth)}
    assert rows["vendor"][3] == "✓"
    assert rows["total"][3] == "✗"
    assert rows["vat_rate"][3] == "✓"  # None == None


def test_eval_report_md_matches_harness_output():
    report = run_offline_eval(GOLDEN, Path("eval_report.json")).to_dict()
    md = eval_report_md(report)
    assert f"Macro F1: {report['macro_f1']:.3f}" in md
    assert "| vendor |" in md
