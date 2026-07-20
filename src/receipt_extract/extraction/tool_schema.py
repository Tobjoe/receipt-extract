"""JSON schema for the ``record_receipt`` tool.

We use Anthropic tool-use (function calling) with a strict input schema rather
than asking the model for free-text JSON. The API validates the model output
against this schema before we ever see it, which removes an entire class of
"model wrapped JSON in prose" parsing failures.
"""

from __future__ import annotations

TOOL_NAME = "record_receipt"

_LINE_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "quantity": {"type": "string", "description": "decimal string, e.g. '2'"},
        "unit_price": {"type": "string", "description": "decimal string per unit"},
        "amount": {"type": "string", "description": "line total = quantity*unit_price"},
    },
    "required": ["description", "quantity", "unit_price", "amount"],
}

_CONFIDENCE_SCHEMA = {
    "type": "object",
    "description": "Per-field confidence in [0,1]; omit fields you are unsure about.",
    "properties": {
        field: {"type": "number", "minimum": 0, "maximum": 1}
        for field in (
            "vendor", "date", "currency", "total",
            "vat_rate", "vat_amount", "payment_method",
        )
    },
}


def build_receipt_tool() -> dict:
    """Return the Anthropic tool definition for structured receipt capture."""
    return {
        "name": TOOL_NAME,
        "description": (
            "Record the structured data extracted from a receipt or invoice "
            "image. Use decimal strings for all monetary values to avoid "
            "floating-point rounding."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "vendor": {"type": "string"},
                "date": {"type": "string", "description": "ISO-8601 date YYYY-MM-DD"},
                "currency": {"type": "string", "description": "ISO-4217 code"},
                "total": {"type": "string", "description": "gross total incl. VAT"},
                "vat_rate": {"type": "string", "description": "percent, e.g. '8.1'"},
                "vat_amount": {"type": "string"},
                "line_items": {"type": "array", "items": _LINE_ITEM_SCHEMA},
                "payment_method": {"type": "string"},
                "confidence": _CONFIDENCE_SCHEMA,
            },
            "required": ["vendor", "date", "currency", "total"],
        },
    }
