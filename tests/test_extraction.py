from types import SimpleNamespace

import pytest

from receipt_extract.extraction import (
    ExtractionFailed,
    ReceiptExtractor,
    build_receipt_tool,
)


def _tool_use_block(payload):
    return SimpleNamespace(type="tool_use", name="record_receipt", input=payload)


def _response(payload, tokens_in=100, tokens_out=50):
    return SimpleNamespace(
        content=[_tool_use_block(payload)],
        usage=SimpleNamespace(input_tokens=tokens_in, output_tokens=tokens_out),
        stop_reason="tool_use",
    )


_GOOD = {
    "vendor": "Cafe Bern",
    "date": "2026-01-15",
    "currency": "CHF",
    "total": "5.00",
    "vat_rate": "8.1",
    "vat_amount": "0.37",
    "line_items": [
        {"description": "Coffee", "quantity": "2", "unit_price": "2.50", "amount": "5.00"}
    ],
    "payment_method": "card",
}


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


def test_build_tool_schema_has_required_fields():
    tool = build_receipt_tool()
    props = tool["input_schema"]["properties"]
    assert "vendor" in props and "line_items" in props
    assert tool["name"] == "record_receipt"


def test_extract_success_first_try(tmp_path):
    img = tmp_path / "r.png"
    img.write_bytes(_PNG_BYTES)
    client = FakeClient([_response(_GOOD)])
    extractor = ReceiptExtractor(client=client, model="claude-x")
    result = extractor.extract(img)
    assert result.receipt.vendor == "Cafe Bern"
    assert result.run.tokens_in == 100
    assert result.run.tokens_out == 50
    assert result.run.attempts == 1
    assert len(client.messages.calls) == 1


def test_extract_retries_on_validation_error(tmp_path):
    img = tmp_path / "r.png"
    img.write_bytes(_PNG_BYTES)
    bad = dict(_GOOD, total="999.00")  # violates total==sum(line_items)
    client = FakeClient([_response(bad), _response(_GOOD)])
    extractor = ReceiptExtractor(client=client, model="claude-x")
    result = extractor.extract(img)
    assert result.receipt.vendor == "Cafe Bern"
    assert result.run.attempts == 2
    assert len(client.messages.calls) == 2
    # second call must include the validation error feedback
    second_msgs = client.messages.calls[1]["messages"]
    assert any("total" in str(m).lower() for m in second_msgs)


def test_extract_gives_up_after_max_retries(tmp_path):
    img = tmp_path / "r.png"
    img.write_bytes(_PNG_BYTES)
    bad = dict(_GOOD, total="999.00")
    client = FakeClient([_response(bad), _response(bad), _response(bad)])
    extractor = ReceiptExtractor(client=client, model="claude-x", max_retries=2)
    with pytest.raises(ExtractionFailed):
        extractor.extract(img)
    assert len(client.messages.calls) == 3


def test_extract_missing_file_raises(tmp_path):
    client = FakeClient([_response(_GOOD)])
    extractor = ReceiptExtractor(client=client, model="claude-x")
    with pytest.raises(FileNotFoundError):
        extractor.extract(tmp_path / "nope.png")


def test_extract_no_tool_use_block_fails(tmp_path):
    img = tmp_path / "r.png"
    img.write_bytes(_PNG_BYTES)
    resp = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="I cannot help")],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        stop_reason="end_turn",
    )
    client = FakeClient([resp])
    extractor = ReceiptExtractor(client=client, model="claude-x")
    with pytest.raises(ExtractionFailed):
        extractor.extract(img)


# Minimal 1x1 PNG.
_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?\x00\x05"
    b"\xfe\x02\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
)
