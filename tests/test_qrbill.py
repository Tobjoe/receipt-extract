from decimal import Decimal

import pytest

from receipt_extract.qrbill import QRBill, QRBillError, parse_qr_bill


def _valid_payload(amount="50.00", currency="CHF", ref_type="QRR",
                   reference="210000000003139471430009017"):
    lines = [
        "SPC", "0200", "1",
        "CH4431999123000889012",  # QR-IBAN
        "S", "Robert Schneider AG", "Rue du Lac", "1268", "2501", "Biel", "CH",
        "", "", "", "", "", "", "",  # ultimate creditor (empty)
        amount, currency,
        "S", "Pia-Maria Rutschmann-Schnyder", "Grosse Marktgasse", "28",
        "9400", "Rorschach", "CH",
        ref_type, reference,
        "Instruction of 15.09.2019",
        "EPD",
    ]
    return "\r\n".join(lines)


class TestParseValid:
    def test_parses_core_fields(self):
        bill = parse_qr_bill(_valid_payload())
        assert isinstance(bill, QRBill)
        assert bill.iban == "CH4431999123000889012"
        assert bill.amount == Decimal("50.00")
        assert bill.currency == "CHF"
        assert bill.creditor == "Robert Schneider AG"
        assert bill.reference_type == "QRR"
        assert bill.reference == "210000000003139471430009017"

    def test_accepts_lf_line_endings(self):
        payload = _valid_payload().replace("\r\n", "\n")
        bill = parse_qr_bill(payload)
        assert bill.currency == "CHF"

    def test_amount_optional(self):
        payload = _valid_payload(amount="")
        bill = parse_qr_bill(payload)
        assert bill.amount is None

    def test_reference_none_type(self):
        payload = _valid_payload(ref_type="NON", reference="")
        bill = parse_qr_bill(payload)
        assert bill.reference_type == "NON"
        assert bill.reference is None


class TestParseMalformed:
    def test_wrong_header_rejected(self):
        payload = _valid_payload().replace("SPC", "XXX", 1)
        with pytest.raises(QRBillError, match="header"):
            parse_qr_bill(payload)

    def test_unsupported_version_rejected(self):
        payload = _valid_payload().replace("0200", "0100", 1)
        with pytest.raises(QRBillError, match="version"):
            parse_qr_bill(payload)

    def test_too_few_fields_rejected(self):
        payload = "SPC\r\n0200\r\n1\r\nCH44"
        with pytest.raises(QRBillError, match="fields"):
            parse_qr_bill(payload)

    def test_invalid_iban_rejected(self):
        payload = _valid_payload().replace("CH4431999123000889012", "DE1234")
        with pytest.raises(QRBillError, match="IBAN"):
            parse_qr_bill(payload)

    def test_invalid_currency_rejected(self):
        payload = _valid_payload(currency="XXX")
        with pytest.raises(QRBillError, match="currency"):
            parse_qr_bill(payload)

    def test_invalid_amount_rejected(self):
        payload = _valid_payload(amount="notanumber")
        with pytest.raises(QRBillError, match="amount"):
            parse_qr_bill(payload)

    def test_missing_trailer_rejected(self):
        payload = _valid_payload().replace("EPD", "XXX")
        with pytest.raises(QRBillError, match="trailer"):
            parse_qr_bill(payload)

    def test_empty_payload_rejected(self):
        with pytest.raises(QRBillError):
            parse_qr_bill("")
