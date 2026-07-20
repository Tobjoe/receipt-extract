"""Load an image or PDF into base64-encoded PNG pages for the vision API."""

from __future__ import annotations

import base64
from pathlib import Path

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_PDF_RENDER_SCALE = 2.0  # ~144 DPI, good enough for receipt OCR


def _encode(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("ascii")


def _render_pdf(path: Path) -> list[str]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    try:
        pages: list[str] = []
        for page in pdf:
            bitmap = page.render(scale=_PDF_RENDER_SCALE)
            pil_image = bitmap.to_pil()
            import io

            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            pages.append(_encode(buffer.getvalue()))
        return pages
    finally:
        pdf.close()


def load_media_pages(path: Path) -> list[str]:
    """Return base64 PNG pages for ``path`` (single image -> one page).

    Raises FileNotFoundError for missing paths and ValueError for unsupported
    file types.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"media file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages = _render_pdf(path)
        if not pages:
            raise ValueError(f"PDF has no renderable pages: {path}")
        return pages
    if suffix in _IMAGE_SUFFIXES:
        return [_encode(path.read_bytes())]
    raise ValueError(f"unsupported media type: {suffix!r}")
