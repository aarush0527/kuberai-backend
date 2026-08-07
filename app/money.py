"""
Every rupee and gold-quantity value in this system is a decimal.Decimal.

Two distinct rules, deliberately different:

- Rupee amounts are USER-STATED. We validate them (<=2dp, positive) and
  REJECT anything that violates that instead of silently rounding: an
  amount someone typed is not ours to reinterpret.
- Gold quantity is SYSTEM-DERIVED (rupee_amount / price). We compute and
  round it ourselves, and there's exactly one rounding rule for that,
  everywhere: ROUND_HALF_UP to 4 decimal places.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


class MoneyError(ValueError):
    """Raised for any money value that fails validation. Carries a
    reason_code so callers can build specific, testable rejections
    instead of pattern-matching error strings."""

    def __init__(self, message: str, reason_code: str):
        super().__init__(message)
        self.reason_code = reason_code


def parse_rupee_amount(raw: str | Decimal) -> Decimal:
    """
    Parse and validate a user-stated rupee amount.

    Rejects (does not silently fix):
      - values that aren't valid numbers                -> AMOUNT_INVALID
      - more than 2 decimal places                       -> AMOUNT_BAD_PRECISION
      - zero or negative amounts                          -> AMOUNT_NOT_POSITIVE

    """
    if isinstance(raw, float):
       
        raise MoneyError("amount must be provided as a string or Decimal, not float", "AMOUNT_INVALID")

    try:
        amount = raw if isinstance(raw, Decimal) else Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        raise MoneyError(f"'{raw}' is not a valid amount", "AMOUNT_INVALID")

    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        raise MoneyError("amount must have at most 2 decimal places", "AMOUNT_BAD_PRECISION")

    if amount <= 0:
        raise MoneyError("amount must be greater than zero", "AMOUNT_NOT_POSITIVE")

    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_gold_quantity(rupee_amount: Decimal, price_per_gram: Decimal) -> Decimal:

    if price_per_gram <= 0:
        raise MoneyError("price must be positive", "PRICE_INVALID")

    raw_quantity = rupee_amount / price_per_gram
    return raw_quantity.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
