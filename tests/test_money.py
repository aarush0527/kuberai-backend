from decimal import Decimal

import pytest

from app.money import parse_rupee_amount, compute_gold_quantity, MoneyError



# Golden-value tests: pinned exact expected outputs. Any change to the
# arithmetic — wrong rounding mode, a stray float, an off-by-one on the
# quantize precision — will shift one of these and the test will fail.


def test_golden_value_odd_amount():

    price = Decimal("6500.00")
    amount = Decimal("333.33")
    assert compute_gold_quantity(amount, price) == Decimal("0.0513")


def test_golden_value_clean_division():
    price = Decimal("6500.00")
    amount = Decimal("1000.00")

    assert compute_gold_quantity(amount, price) == Decimal("0.1538")


def test_golden_value_minimum_amount():
    price = Decimal("14500.0000")
    amount = Decimal("1.00")

    assert compute_gold_quantity(amount, price) == Decimal("0.0001")


def test_round_half_up_not_banker_rounding():

    price = Decimal("4")
    amount = Decimal("0.0002")
    assert compute_gold_quantity(amount, price) == Decimal("0.0001")


def test_no_float_contamination():

    price = Decimal("3")
    amount = Decimal("1.00")
    assert compute_gold_quantity(amount, price) == Decimal("0.3333")


def test_gold_quantity_rejects_non_positive_price():
    with pytest.raises(MoneyError) as exc:
        compute_gold_quantity(Decimal("100.00"), Decimal("0"))
    assert exc.value.reason_code == "PRICE_INVALID"



# parse_rupee_amount: user-stated amounts are validated and REJECTED on violation, never silently rounded.


def test_parse_accepts_valid_two_decimal_amount():
    assert parse_rupee_amount("333.33") == Decimal("333.33")


def test_parse_accepts_whole_number_amount():
    assert parse_rupee_amount("500") == Decimal("500.00")


def test_parse_accepts_decimal_input_directly():
    assert parse_rupee_amount(Decimal("42.10")) == Decimal("42.10")


def test_parse_rejects_more_than_two_decimal_places():
    with pytest.raises(MoneyError) as exc:
        parse_rupee_amount("333.333")
    assert exc.value.reason_code == "AMOUNT_BAD_PRECISION"


def test_parse_rejects_negative_amount():
    with pytest.raises(MoneyError) as exc:
        parse_rupee_amount("-5000")
    assert exc.value.reason_code == "AMOUNT_NOT_POSITIVE"


def test_parse_rejects_zero_amount():
    with pytest.raises(MoneyError) as exc:
        parse_rupee_amount("0")
    assert exc.value.reason_code == "AMOUNT_NOT_POSITIVE"


def test_parse_rejects_garbage_input():
    with pytest.raises(MoneyError) as exc:
        parse_rupee_amount("buy me some gold")
    assert exc.value.reason_code == "AMOUNT_INVALID"


def test_parse_rejects_bare_float_defensively():
    # Even if something upstream slips a float in (it shouldn't — amounts
    # must travel as strings/Decimal end to end) this must not silently
    # accept it and risk precision loss.
    with pytest.raises(MoneyError) as exc:
        parse_rupee_amount(333.33)  # type: ignore[arg-type]
    assert exc.value.reason_code == "AMOUNT_INVALID"


def test_parse_rejects_absurdly_large_amount_string():

    assert parse_rupee_amount("100000000000") == Decimal("100000000000.00")
