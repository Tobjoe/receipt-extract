"""Gradio web UI: live extraction (with a key) + offline demo & evaluation.

Run with::

    receipt-extract-ui            # or: python -m receipt_extract.webui.app

Live extraction needs ``ANTHROPIC_API_KEY``. Without a key the UI still runs:
the "Offline demo" and "Evaluation" tabs work fully against the golden dataset
and make zero API calls.
"""

from __future__ import annotations

import os
from pathlib import Path

import gradio as gr

from receipt_extract.cli import DEFAULT_MODEL
from receipt_extract.eval import run_offline_eval
from receipt_extract.webui.render import (
    diff_rows,
    eval_report_md,
    line_item_rows,
    list_golden_stems,
    load_receipt_dict,
    receipt_summary_md,
)

GOLDEN_DIR = Path("data/golden")
_LINE_ITEM_HEADERS = ["description", "quantity", "unit_price", "amount"]
_DIFF_HEADERS = ["field", "predicted", "ground truth", "match"]


def _has_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def extract_live(file_path: str | None, model: str):
    """Run a real vision extraction on an uploaded image/PDF."""
    if not file_path:
        return "Upload an image or PDF first.", [], {}
    if not _has_key():
        return (
            "**No `ANTHROPIC_API_KEY` set.** Live extraction is disabled — "
            "use the *Offline demo* tab to explore recorded results with zero "
            "API calls.",
            [],
            {},
        )
    # Import lazily so the UI (and its tests) never require the anthropic client.
    import anthropic

    from receipt_extract.extraction import ExtractionFailed, ReceiptExtractor

    extractor = ReceiptExtractor(
        client=anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"]),
        model=model,
    )
    try:
        result = extractor.extract(Path(file_path))
    except (ExtractionFailed, ValueError, FileNotFoundError) as exc:
        return f"**Extraction failed:** {exc}", [], {}

    data = result.receipt.model_dump(mode="json")
    run = result.run
    summary = (
        f"{receipt_summary_md(data)}\n\n"
        f"*model `{run.model}` · {run.attempts} attempt(s) · "
        f"{run.tokens_in}→{run.tokens_out} tokens · {run.latency_ms} ms*"
    )
    return summary, line_item_rows(data), data


def load_offline_sample(stem: str | None):
    """Show a recorded prediction vs ground truth for one golden sample."""
    if not stem:
        return "Pick a sample.", [], []
    pred = load_receipt_dict(GOLDEN_DIR / f"{stem}.pred.json")
    truth = load_receipt_dict(GOLDEN_DIR / f"{stem}.truth.json")
    header = (
        f"### `{stem}`\n"
        "Recorded model prediction vs. hand-labelled ground truth — no API call."
    )
    return header, line_item_rows(pred), diff_rows(pred, truth)


def run_eval():
    """Score the whole golden dataset offline and render the scorecard."""
    report = run_offline_eval(GOLDEN_DIR, Path("eval_report.json"))
    return eval_report_md(report.to_dict())


def build_app() -> gr.Blocks:
    stems = list_golden_stems(GOLDEN_DIR)
    key_banner = (
        "🟢 `ANTHROPIC_API_KEY` detected — live extraction enabled."
        if _has_key()
        else "⚪ No API key — live tab is a stub; offline tabs work fully."
    )

    with gr.Blocks(title="receipt-extract", theme=gr.themes.Soft()) as app:
        gr.Markdown(
            "# 🧾 receipt-extract\n"
            "Image / PDF → vision LLM (tool-use) → **schema-validated** data. "
            f"\n\n{key_banner}"
        )

        with gr.Tab("Extract (live)"):
            with gr.Row():
                with gr.Column():
                    file_in = gr.File(
                        label="Receipt image or PDF",
                        file_types=["image", ".pdf"],
                        type="filepath",
                    )
                    model_in = gr.Textbox(label="Model", value=DEFAULT_MODEL)
                    extract_btn = gr.Button("Extract", variant="primary")
                with gr.Column():
                    live_summary = gr.Markdown()
                    live_items = gr.Dataframe(
                        headers=_LINE_ITEM_HEADERS, label="Line items", wrap=True
                    )
                    live_json = gr.JSON(label="Validated receipt")
            extract_btn.click(
                extract_live,
                inputs=[file_in, model_in],
                outputs=[live_summary, live_items, live_json],
            )

        with gr.Tab("Offline demo"):
            gr.Markdown(
                "Explore the golden dataset — recorded predictions checked "
                "against ground truth, field by field. Zero API calls."
            )
            sample_in = gr.Dropdown(
                choices=stems, value=stems[0] if stems else None, label="Golden sample"
            )
            sample_header = gr.Markdown()
            with gr.Row():
                sample_items = gr.Dataframe(
                    headers=_LINE_ITEM_HEADERS, label="Predicted line items", wrap=True
                )
                sample_diff = gr.Dataframe(
                    headers=_DIFF_HEADERS, label="Field-by-field diff", wrap=True
                )
            sample_in.change(
                load_offline_sample,
                inputs=sample_in,
                outputs=[sample_header, sample_items, sample_diff],
            )

        with gr.Tab("Evaluation"):
            gr.Markdown(
                "Run the offline harness over every golden receipt and score "
                "each field (precision / recall / F1)."
            )
            eval_btn = gr.Button("Run evaluation", variant="primary")
            eval_out = gr.Markdown()
            eval_btn.click(run_eval, outputs=eval_out)

    return app


def main() -> None:
    build_app().launch()


if __name__ == "__main__":
    main()
