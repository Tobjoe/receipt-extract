import base64

import pytest

from receipt_extract.extraction.media import load_media_pages

_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xff\xff?\x00\x05"
    b"\xfe\x02\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_loads_png_as_single_base64_page(tmp_path):
    img = tmp_path / "r.png"
    img.write_bytes(_PNG)
    pages = load_media_pages(img)
    assert len(pages) == 1
    assert base64.standard_b64decode(pages[0]) == _PNG


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_media_pages(tmp_path / "nope.png")


def test_unsupported_type_raises(tmp_path):
    bad = tmp_path / "r.txt"
    bad.write_text("hi")
    with pytest.raises(ValueError, match="unsupported"):
        load_media_pages(bad)


def test_renders_pdf_via_pypdfium2(tmp_path):
    # Build a minimal one-page PDF using Pillow, then render it back.
    from PIL import Image

    pdf = tmp_path / "doc.pdf"
    Image.new("RGB", (50, 50), "white").save(pdf, format="PDF")
    pages = load_media_pages(pdf)
    assert len(pages) == 1
    assert base64.standard_b64decode(pages[0]).startswith(b"\x89PNG")
