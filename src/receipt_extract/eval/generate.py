"""Generate a synthetic golden dataset (PNG + ground truth + recorded prediction).

Everything is synthetic. For each receipt we write:
- ``<name>.png``        rendered receipt (Pillow, headless)
- ``<name>.truth.json`` ground-truth Receipt
- ``<name>.pred.json``  recorded stub-extractor prediction (may contain errors)
- ``<name>.png.spc``    Swiss QR-bill sidecar (only for QR receipts)

The prediction files let the offline eval produce real, non-trivial metrics
without any API calls. Hard receipts get deliberately injected prediction errors.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw

from receipt_extract.models import LineItem, Receipt

_W, _H = 380, 520
_LINE_H = 22


@dataclass(frozen=True)
class Spec:
    name: str
    receipt: Receipt
    qr_payload: str | None = None
    pred_overrides: dict = field(default_factory=dict)


def _li(desc, qty, price):
    q, p = Decimal(qty), Decimal(price)
    return LineItem(description=desc, quantity=q, unit_price=p, amount=q * p)


def _render_png(receipt: Receipt, out: Path) -> None:
    img = Image.new("RGB", (_W, _H), "white")
    draw = ImageDraw.Draw(img)
    y = 16
    draw.text((16, y), receipt.vendor, fill="black")
    y += _LINE_H
    draw.text((16, y), f"Date: {receipt.date.isoformat()}", fill="black")
    y += _LINE_H * 2
    for li in receipt.line_items:
        draw.text((16, y), f"{li.quantity} x {li.description}", fill="black")
        draw.text((260, y), f"{li.amount} {receipt.currency}", fill="black")
        y += _LINE_H
    y += _LINE_H
    draw.text((16, y), f"TOTAL: {receipt.total} {receipt.currency}", fill="black")
    if receipt.vat_rate is not None:
        y += _LINE_H
        draw.text((16, y), f"VAT {receipt.vat_rate}%: {receipt.vat_amount}", fill="black")
    img.save(out, format="PNG")


def _write_json(path: Path, receipt: Receipt) -> None:
    path.write_text(json.dumps(receipt.model_dump(mode="json"), indent=2), "utf-8")


def generate_golden(out_dir: Path, specs: list[Spec] | None = None) -> list[Path]:
    """Render all specs into ``out_dir``; return the list of PNG paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = specs or build_specs()
    pngs: list[Path] = []
    for spec in specs:
        png = out_dir / f"{spec.name}.png"
        _render_png(spec.receipt, png)
        _write_json(out_dir / f"{spec.name}.truth.json", spec.receipt)
        # Re-validate the prediction so injected errors stay internally
        # consistent (model_copy alone skips validators).
        pred = Receipt.model_validate(
            spec.receipt.model_copy(update=spec.pred_overrides).model_dump()
        )
        _write_json(out_dir / f"{spec.name}.pred.json", pred)
        if spec.qr_payload is not None:
            (out_dir / f"{spec.name}.png.spc").write_text(spec.qr_payload, "utf-8")
        pngs.append(png)
    return pngs


def _qr_payload(iban, amount, currency, creditor, reference):
    return "\r\n".join([
        "SPC", "0200", "1", iban,
        "S", creditor, "Rue du Lac", "1268", "2501", "Biel", "CH",
        "", "", "", "", "", "", "",
        amount, currency,
        "S", "Debtor Name", "Street", "1", "9400", "Rorschach", "CH",
        "QRR", reference, "", "EPD",
    ])


def build_specs() -> list[Spec]:  # noqa: PLR0915 - flat data table
    return _EASY_SPECS() + _QR_SPECS() + _HARD_SPECS()


def _EASY_SPECS() -> list[Spec]:
    r1 = Receipt(vendor="Cafe Bern", date=date(2026, 1, 15), currency="CHF",
                 total=Decimal("12.50"),
                 line_items=[_li("Coffee", "2", "2.50"), _li("Croissant", "1", "7.50")],
                 payment_method="card")
    r2 = Receipt(vendor="Migros", date=date(2026, 2, 3), currency="CHF",
                 total=Decimal("23.40"),
                 line_items=[_li("Milk", "2", "1.70"), _li("Bread", "4", "5.00")],
                 payment_method="cash")
    r3 = Receipt(vendor="SBB", date=date(2026, 3, 10), currency="CHF",
                 total=Decimal("75.00"),
                 line_items=[_li("Ticket ZH-BE", "1", "75.00")], payment_method="card")
    r4 = Receipt(vendor="Denner", date=date(2026, 1, 22), currency="CHF",
                 total=Decimal("9.90"),
                 line_items=[_li("Wine", "1", "9.90")], payment_method="card")
    r5 = Receipt(vendor="Starbucks", date=date(2026, 2, 14), currency="EUR",
                 total=Decimal("8.80"),
                 line_items=[_li("Latte", "2", "4.40")], payment_method="card")
    return [Spec(f"easy_{i}", r) for i, r in enumerate([r1, r2, r3, r4, r5], 1)]


def _QR_SPECS() -> list[Spec]:
    r1 = Receipt(vendor="Elektro AG", date=date(2026, 1, 30), currency="CHF",
                 total=Decimal("250.00"),
                 line_items=[_li("Installation", "1", "250.00")])
    p1 = _qr_payload("CH4431999123000889012", "250.00", "CHF",
                     "Elektro AG", "210000000003139471430009017")
    r2 = Receipt(vendor="Sanitaer GmbH", date=date(2026, 2, 5), currency="CHF",
                 total=Decimal("480.00"),
                 line_items=[_li("Repair", "1", "480.00")])
    p2 = _qr_payload("CH5800791123000889012", "480.00", "CHF",
                     "Sanitaer GmbH", "210000000003139471430009018")
    r3 = Receipt(vendor="Garten AG", date=date(2026, 3, 1), currency="CHF",
                 total=Decimal("120.00"),
                 line_items=[_li("Hedge trim", "1", "120.00")])
    p3 = _qr_payload("CH9300762011623852957", "120.00", "CHF",
                     "Garten AG", "210000000003139471430009019")
    return [
        Spec("qr_1", r1, qr_payload=p1),
        Spec("qr_2", r2, qr_payload=p2),
        Spec("qr_3", r3, qr_payload=p3),
    ]


def _HARD_SPECS() -> list[Spec]:
    # Hard 1: faded VAT -> stub mispredicts vat_amount.
    hard1 = Receipt(vendor="Restaurant Krone", date=date(2026, 2, 20), currency="CHF",
                    total=Decimal("64.80"), vat_rate=Decimal("8.1"),
                    vat_amount=Decimal("4.86"),
                    line_items=[_li("Menu", "2", "32.40")], payment_method="card")
    # Hard 2: messy multi-item -> stub drops a line item and gets vendor case wrong.
    hard2 = Receipt(vendor="Coop Pronto", date=date(2026, 3, 8), currency="CHF",
                    total=Decimal("18.60"),
                    line_items=[_li("Sandwich", "1", "6.60"),
                                _li("Juice", "2", "3.00"),
                                _li("Chips", "1", "6.00")], payment_method="cash")
    # hard1 pred keeps a consistent but wrong VAT rate/amount pair (2.5% guess).
    return [
        Spec("hard_1", hard1,
             pred_overrides={"vat_rate": Decimal("2.5"),
                             "vat_amount": Decimal("1.58")}),
        Spec("hard_2", hard2,
             pred_overrides={"date": date(2026, 3, 18),
                             "line_items": [_li("Sandwich", "1", "6.60"),
                                            _li("Juice", "2", "3.00")],
                             "total": Decimal("12.60")}),
    ]
