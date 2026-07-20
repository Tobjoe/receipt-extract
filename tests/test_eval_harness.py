import json
from pathlib import Path

from receipt_extract.eval import run_offline_eval
from receipt_extract.eval.generate import generate_golden


def test_generate_creates_all_artifacts(tmp_path):
    generate_golden(tmp_path)
    pngs = list(tmp_path.glob("*.png"))
    truths = list(tmp_path.glob("*.truth.json"))
    preds = list(tmp_path.glob("*.pred.json"))
    spcs = list(tmp_path.glob("*.spc"))
    assert len(pngs) == 10
    assert len(truths) == 10
    assert len(preds) == 10
    assert len(spcs) == 3  # three QR receipts
    # PNGs are non-empty real image files
    assert all(p.stat().st_size > 100 for p in pngs)


def test_offline_eval_produces_report(tmp_path):
    generate_golden(tmp_path)
    out = tmp_path / "report.json"
    report = run_offline_eval(tmp_path, out)
    assert report.n_receipts == 10
    assert 0.0 < report.macro_f1 < 1.0  # non-trivial: some fields wrong
    data = json.loads(out.read_text())
    assert data["fields"]["vendor"]["f1"] == 1.0
    assert data["fields"]["vat_amount"]["f1"] < 1.0


def test_render_table_contains_fields(tmp_path):
    generate_golden(tmp_path)
    report = run_offline_eval(tmp_path, tmp_path / "r.json")
    table = report.render_table()
    assert "vendor" in table
    assert "MACRO-F1" in table


def test_repo_golden_dir_is_populated():
    golden = Path(__file__).resolve().parents[1] / "data" / "golden"
    assert len(list(golden.glob("*.truth.json"))) == 10
