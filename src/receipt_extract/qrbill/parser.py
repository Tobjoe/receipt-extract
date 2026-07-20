"""Deterministic parser for the Swiss QR-bill (SIX standard v2.0) payload.

The QR-bill embeds a fixed-order, newline-separated text payload starting with
the ``SPC`` header. This module parses that payload into a validated
:class:`QRBill`. It is intentionally dependency-light and fully deterministic;
no network or LLM involved.

Reference: Swiss Payment Standards, "Swiss QR Code" specification.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Fixed offsets into the newline-separated payload (0-based).
_HEADER = 0
_VERSION = 1
_IBAN = 3
_CREDITOR_NAME = 5
_AMOUNT = 18
_CURRENCY = 19
_REF_TYPE = 27
_REFERENCE = 28
_TRAILER = 30

_MIN_FIELDS = 31
_SUPPORTED_VERSIONS = {"0200", "0210"}
_VALID_CURRENCIES = {"CHF", "EUR"}
_VALID_REF_TYPES = {"QRR", "SCOR", "NON"}


class QRBillError(ValueError):
    """Raised when a QR-bill payload is malformed or unsupported."""


@dataclass(frozen=True)
class QRBill:
    """Structured, validated Swiss QR-bill data."""

    iban: str
    amount: Decimal | None
    currency: str
    creditor: str
    reference_type: str
    reference: str | None


def _validate_iban(raw: str) -> str:
    iban = raw.replace(" ", "").upper()
    if not iban.startswith(("CH", "LI")) or not (16 <= len(iban) <= 21):
        raise QRBillError(f"invalid Swiss IBAN: {raw!r}")
    if not iban[2:].isdigit():
        raise QRBillError(f"invalid IBAN check/body digits: {raw!r}")
    return iban


def _parse_amount(raw: str) -> Decimal | None:
    if raw.strip() == "":
        return None
    try:
        return Decimal(raw.strip())
    except InvalidOperation as exc:
        raise QRBillError(f"invalid amount: {raw!r}") from exc


def parse_qr_bill(payload: str) -> QRBill:
    """Parse an SPC QR-bill payload into a :class:`QRBill`.

    Raises :class:`QRBillError` for any structural or value problem.
    """
    if not payload or not payload.strip():
        raise QRBillError("empty QR-bill payload")

    fields = payload.replace("\r\n", "\n").split("\n")
    if len(fields) < _MIN_FIELDS:
        raise QRBillError(
            f"too few fields: got {len(fields)}, need at least {_MIN_FIELDS}"
        )

    if fields[_HEADER] != "SPC":
        raise QRBillError(f"invalid header: expected 'SPC', got {fields[_HEADER]!r}")

    if fields[_VERSION] not in _SUPPORTED_VERSIONS:
        raise QRBillError(f"unsupported version: {fields[_VERSION]!r}")

    if fields[_TRAILER] != "EPD":
        raise QRBillError(f"invalid trailer: expected 'EPD', got {fields[_TRAILER]!r}")

    currency = fields[_CURRENCY].strip().upper()
    if currency not in _VALID_CURRENCIES:
        raise QRBillError(f"invalid currency: {currency!r} (QR-bill allows CHF/EUR)")

    ref_type = fields[_REF_TYPE].strip().upper()
    if ref_type not in _VALID_REF_TYPES:
        raise QRBillError(f"invalid reference type: {ref_type!r}")

    reference = fields[_REFERENCE].strip() or None
    if ref_type == "NON":
        reference = None

    return QRBill(
        iban=_validate_iban(fields[_IBAN]),
        amount=_parse_amount(fields[_AMOUNT]),
        currency=currency,
        creditor=fields[_CREDITOR_NAME].strip(),
        reference_type=ref_type,
        reference=reference,
    )
