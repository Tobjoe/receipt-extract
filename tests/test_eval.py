from datetime import date
from decimal import Decimal

from receipt_extract.eval.scoring import FieldScore, score_scalar_field, values_match
from receipt_extract.models import LineItem, Receipt


def _receipt(**over):
    base = dict(
        vendor="Cafe Bern",
        date=date(2026, 1, 15),
        currency="CHF",
        total=Decimal("5.00"),
        line_items=[
            LineItem(description="Coffee", quantity=Decimal("2"),
                     unit_price=Decimal("2.50"), amount=Decimal("5.00"))
        ],
    )
    base.update(over)
    return Receipt(**base)


class TestValuesMatch:
    def test_exact_string_match(self):
        assert values_match("currency", "CHF", "CHF")

    def test_case_insensitive_vendor(self):
        assert values_match("vendor", "cafe bern", "Cafe Bern")

    def test_money_within_tolerance(self):
        assert values_match("total", Decimal("5.03"), Decimal("5.00"))

    def test_money_outside_tolerance(self):
        assert not values_match("total", Decimal("6.00"), Decimal("5.00"))

    def test_none_does_not_match_value(self):
        assert not values_match("total", None, Decimal("5.00"))

    def test_none_matches_none(self):
        assert values_match("vat_rate", None, None)


class TestScoreScalarField:
    def test_perfect_predictions(self):
        preds = [_receipt(), _receipt(vendor="Migros")]
        truths = [_receipt(), _receipt(vendor="Migros")]
        score = score_scalar_field("vendor", preds, truths)
        assert score.precision == 1.0
        assert score.recall == 1.0
        assert score.f1 == 1.0

    def test_one_wrong_prediction(self):
        preds = [_receipt(vendor="WRONG"), _receipt(vendor="Migros")]
        truths = [_receipt(vendor="Cafe Bern"), _receipt(vendor="Migros")]
        score = score_scalar_field("vendor", preds, truths)
        assert score.precision == 0.5
        assert score.recall == 0.5

    def test_missing_prediction_hurts_recall_not_precision(self):
        # vat_rate present in truth, absent in prediction
        preds = [_receipt(vat_rate=None)]
        truths = [_receipt(vat_rate=Decimal("8.1"), vat_amount=Decimal("0.37"))]
        score = score_scalar_field("vat_rate", preds, truths)
        assert score.recall == 0.0

    def test_field_score_is_dataclass(self):
        score = FieldScore(field="x", precision=1.0, recall=1.0, f1=1.0,
                           tp=1, fp=0, fn=0)
        assert score.field == "x"
