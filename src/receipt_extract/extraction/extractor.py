"""Vision-LLM receipt extractor with a validation-driven retry loop.

The model is forced to call the ``record_receipt`` tool. Its structured input is
validated against the Pydantic :class:`Receipt` model. On a ValidationError we
feed the exact error text back to the model (tool_result) and let it correct
itself, up to ``max_retries`` times, before raising :class:`ExtractionFailed`.

The Anthropic client is injected so tests can pass a fake with no network.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from receipt_extract.extraction.media import load_media_pages
from receipt_extract.extraction.tool_schema import TOOL_NAME, build_receipt_tool
from receipt_extract.models import Receipt

logger = logging.getLogger(__name__)

_MAX_TOKENS = 1024
_SYSTEM_PROMPT = (
    "You are a meticulous receipt-extraction assistant. Read the receipt image "
    "and call the record_receipt tool with the exact data you see. Use decimal "
    "strings for money. If a validation error is reported, fix only the offending "
    "fields and call the tool again."
)


class ExtractionFailed(RuntimeError):
    """Raised when extraction fails after exhausting retries."""


@dataclass(frozen=True)
class ExtractionRun:
    """Metadata about a single extraction invocation."""

    model: str
    attempts: int
    tokens_in: int
    tokens_out: int
    latency_ms: int


@dataclass(frozen=True)
class ExtractionResult:
    receipt: Receipt
    run: ExtractionRun


def _find_tool_use(response) -> dict | None:
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == TOOL_NAME:
            return block.input
    return None


def _image_content(pages: list[str]) -> list[dict]:
    return [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": data},
        }
        for data in pages
    ]


class ReceiptExtractor:
    """Extract a :class:`Receipt` from an image/PDF using an injected client."""

    def __init__(self, client, model: str, max_retries: int = 2) -> None:
        self._client = client
        self._model = model
        self._max_retries = max_retries
        self._tool = build_receipt_tool()

    def extract(self, path: Path) -> ExtractionResult:
        pages = load_media_pages(Path(path))
        messages = [
            {
                "role": "user",
                "content": [
                    *_image_content(pages),
                    {"type": "text", "text": "Extract this receipt."},
                ],
            }
        ]
        return self._run_loop(messages)

    def _run_loop(self, messages: list[dict]) -> ExtractionResult:
        start = time.monotonic()
        tokens_in = tokens_out = 0
        last_error = "no tool_use block returned"

        for attempt in range(1, self._max_retries + 2):
            response = self._client.messages.create(
                model=self._model,
                max_tokens=_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                tools=[self._tool],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=messages,
            )
            tokens_in += response.usage.input_tokens
            tokens_out += response.usage.output_tokens

            payload = _find_tool_use(response)
            if payload is None:
                last_error = "model did not call record_receipt"
                break

            try:
                receipt = Receipt.model_validate(payload)
            except ValidationError as exc:
                last_error = str(exc)
                messages = _append_correction(messages, payload, last_error)
                continue

            latency = int((time.monotonic() - start) * 1000)
            run = ExtractionRun(
                model=self._model,
                attempts=attempt,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency,
            )
            return ExtractionResult(receipt=receipt, run=run)

        logger.error("extraction failed after retries: %s", last_error)
        raise ExtractionFailed(last_error)


def _append_correction(messages: list[dict], payload: dict, error: str) -> list[dict]:
    """Return a new message list echoing the bad tool call + validation error."""
    tool_use_id = "call_retry"
    assistant = {
        "role": "assistant",
        "content": [
            {"type": "tool_use", "id": tool_use_id, "name": TOOL_NAME, "input": payload}
        ],
    }
    correction = {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "is_error": True,
                "content": f"Validation failed. Fix these errors and retry:\n{error}",
            }
        ],
    }
    return [*messages, assistant, correction]
