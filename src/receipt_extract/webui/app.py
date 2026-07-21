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


def extract_live(file_path: str | None, model: str, api_key: str | None):
    """Run a real vision extraction on an uploaded image/PDF.

    The key comes from the UI field if the user pasted one, else from the
    ``ANTHROPIC_API_KEY`` environment variable. It is never logged or persisted.
    """
    key = (api_key or "").strip() or os.environ.get("ANTHROPIC_API_KEY", "")
    if not file_path:
        return "Upload an image or PDF first.", [], {}
    if not key:
        return (
            "**No API key.** Paste your `ANTHROPIC_API_KEY` in the field on the "
            "left, or explore the *Offline demo* / *Evaluation* tabs — they need "
            "no key.",
            [],
            {},
        )
    # Import lazily so the UI (and its tests) never require the anthropic client.
    import anthropic

    from receipt_extract.extraction import ExtractionFailed, ReceiptExtractor

    extractor = ReceiptExtractor(
        client=anthropic.Anthropic(api_key=key),
        model=model,
    )
    try:
        result = extractor.extract(Path(file_path))
    except (ExtractionFailed, ValueError, FileNotFoundError) as exc:
        return f"**Extraction failed:** {exc}", [], {}
    except anthropic.APIError as exc:
        # Bad key, rate limit, network — surface it without leaking a traceback.
        return f"**API error:** {exc}", [], {}

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
    has_key = _has_key()
    banner = (
        "> 🟢 **Live extraction is on** — `ANTHROPIC_API_KEY` detected. "
        "Upload a receipt in the first tab."
        if has_key
        else "> ⚪ **No API key in the environment.** Paste one in the *Extract* "
        "tab to run live, or use **Offline demo** / **Evaluation** — they need "
        "no key at all."
    )

    with gr.Blocks(
        title="receipt-extract",
        theme=gr.themes.Soft(primary_hue="emerald", neutral_hue="slate"),
        css=".gradio-container {max-width: 1040px !important; margin: 0 auto;}",
    ) as app:
        gr.Markdown(
            "# 🧾 receipt-extract\n"
            "Turn a **receipt or invoice** (image / PDF) into "
            "**schema-validated, queryable data** — vision LLM + strict Pydantic "
            "checks + an honest evaluation harness.\n\n"
            f"{banner}"
        )

        with gr.Tab("① Extract (live)"):
            gr.Markdown(
                "Upload one receipt and run a **real** extraction. "
                "This calls the Anthropic API (costs a few cents per receipt) "
                "and needs `ANTHROPIC_API_KEY`."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    file_in = gr.File(
                        label="Receipt image or PDF",
                        file_types=["image", ".pdf"],
                        type="filepath",
                    )
                    key_in = gr.Textbox(
                        label="Anthropic API key",
                        type="password",
                        placeholder="sk-ant-…",
                        value="",
                        info=(
                            "Used only for this request — never logged or stored. "
                            "Leave blank to use the ANTHROPIC_API_KEY environment "
                            "variable."
                            + ("  ✓ found in environment" if has_key else "")
                        ),
                    )
                    model_in = gr.Textbox(
                        label="Model", value=DEFAULT_MODEL,
                        info="Anthropic model id used for extraction",
                    )
                    with gr.Row():
                        extract_btn = gr.Button("Extract receipt", variant="primary")
                        clear_btn = gr.ClearButton(value="Clear")
                with gr.Column(scale=1):
                    live_summary = gr.Markdown(
                        "*Upload a receipt, add your key if needed, then "
                        "**Extract**. Results appear here.*"
                    )
                    live_items = gr.Dataframe(
                        headers=_LINE_ITEM_HEADERS, label="Line items",
                        wrap=True, row_count=(1, "dynamic"),
                    )
                    live_json = gr.JSON(label="Validated receipt")
            extract_btn.click(
                extract_live,
                inputs=[file_in, model_in, key_in],
                outputs=[live_summary, live_items, live_json],
            )
            # Clear the file and outputs but keep the key field intact.
            clear_btn.add([file_in, live_summary, live_items, live_json])

        with gr.Tab("② Offline demo"):
            gr.Markdown(
                f"Explore the **{len(stems)} golden receipts** shipped with the "
                "repo — a recorded model prediction checked against "
                "hand-labelled ground truth, field by field. **Zero API "
                "calls.** ✓ = match, ✗ = mismatch."
            )
            sample_in = gr.Dropdown(
                choices=stems, value=stems[0] if stems else None,
                label="Golden sample",
                info="easy_* = clean receipts · hard_* = tricky · qr_* = Swiss QR-bill",
            )
            sample_header = gr.Markdown()
            with gr.Row():
                sample_items = gr.Dataframe(
                    headers=_LINE_ITEM_HEADERS, label="Predicted line items",
                    wrap=True,
                )
                sample_diff = gr.Dataframe(
                    headers=_DIFF_HEADERS, label="Prediction vs. ground truth",
                    wrap=True,
                )
            sample_in.change(
                load_offline_sample,
                inputs=sample_in,
                outputs=[sample_header, sample_items, sample_diff],
            )

        with gr.Tab("③ Evaluation"):
            gr.Markdown(
                "Score **every** golden receipt at once — per-field precision / "
                "recall / F1, plus the macro-average. This is what makes changes "
                "measurable instead of guesswork. Runs offline."
            )
            eval_btn = gr.Button("Re-run evaluation", variant="primary")
            eval_out = gr.Markdown()
            eval_btn.click(run_eval, outputs=eval_out)

        # Populate the offline tabs on load so a keyless visitor sees real
        # results immediately, without hunting for a button to press.
        if stems:
            app.load(
                load_offline_sample,
                inputs=sample_in,
                outputs=[sample_header, sample_items, sample_diff],
            )
        app.load(run_eval, outputs=eval_out)

    return app


def main() -> None:
    build_app().launch(inbrowser=True)


if __name__ == "__main__":
    main()
