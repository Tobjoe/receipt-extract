"""Optional Gradio web UI for extraction demos and offline evaluation.

The pure rendering/loading helpers live in :mod:`receipt_extract.webui.render`
and have no Gradio dependency (so they stay unit-testable). The Gradio wiring
lives in :mod:`receipt_extract.webui.app` and is imported lazily.
"""

from receipt_extract.webui.render import (
    SCALAR_FIELDS,
    diff_rows,
    eval_report_md,
    line_item_rows,
    list_golden_stems,
    load_receipt_dict,
    receipt_summary_md,
)

__all__ = [
    "SCALAR_FIELDS",
    "diff_rows",
    "eval_report_md",
    "line_item_rows",
    "list_golden_stems",
    "load_receipt_dict",
    "receipt_summary_md",
]
