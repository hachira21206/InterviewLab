"""Unit tests for centralized score rounding contract (ROUND_HALF_UP)."""

import math
from decimal import Decimal
import pytest

from app.core.rounding import (
    to_decimal,
    round_half_up_decimal,
    round_score,
    round_average_score,
    round_delta,
)


def test_round_case_1_26_75_div_10():
    """Case 1: 26.75 / 10 = 2.675 -> 2.68 (ROUND_HALF_UP, Python float round would be 2.67)."""
    avg = round_average_score(26.75, 10)
    assert avg == 2.68


def test_round_case_2_27_25_div_10():
    """Case 2: 27.25 / 10 = 2.725 -> 2.73."""
    avg = round_average_score(27.25, 10)
    assert avg == 2.73


def test_round_case_3_72_25_div_10():
    """Case 3: 72.25 / 10 = 7.225 -> 7.23 (ROUND_HALF_UP, Python float round would be 7.22)."""
    avg = round_average_score(72.25, 10)
    assert avg == 7.23


def test_round_case_4_72_75_div_10():
    """Case 4: 72.75 / 10 = 7.275 -> 7.28."""
    avg = round_average_score(72.75, 10)
    assert avg == 7.28


def test_round_case_5_zero():
    """Case 5: 0 score and average -> 0.0."""
    assert round_score(0) == 0.0
    assert round_score(0.0) == 0.0
    assert round_average_score(0.0, 10) == 0.0


def test_round_case_6_100():
    """Case 6: 100 score and average -> 100.0, 10.0."""
    assert round_score(100) == 100.0
    assert round_score(100.0) == 100.0
    assert round_average_score(100.0, 10) == 10.0


def test_round_case_7_positive_delta_001():
    """Case 7: Exactly +0.01 delta -> 0.01."""
    delta = round_delta(7.23, 7.22)
    assert delta == 0.01
    delta_total = round_delta(72.25, 72.24)
    assert delta_total == 0.01


def test_round_case_8_negative_delta_001():
    """Case 8: Exactly -0.01 delta -> -0.01."""
    delta = round_delta(7.22, 7.23)
    assert delta == -0.01
    delta_total = round_delta(72.24, 72.25)
    assert delta_total == -0.01


def test_round_case_9_nan_rejected():
    """Case 9: NaN rejected with ValueError."""
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        to_decimal(float("nan"))
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        round_score(float("nan"))
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        round_average_score(float("nan"), 10)
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        round_delta(float("nan"), 5.0)
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        round_delta(5.0, float("nan"))


def test_round_case_10_infinity_rejected():
    """Case 10: Infinity rejected with ValueError."""
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        to_decimal(float("inf"))
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        to_decimal(float("-inf"))
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        round_score(float("inf"))
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        round_average_score(float("-inf"), 10)
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        round_delta(float("inf"), 1.0)


def test_round_half_away_from_zero_negative():
    """Negative values round half away from zero."""
    assert round_score(-2.675) == -2.68
    assert round_delta(2.67, 5.345) == -2.68


def test_round_average_invalid_count():
    """Count <= 0 raises ValueError."""
    with pytest.raises(ValueError, match="Count must be greater than 0"):
        round_average_score(50.0, 0)
    with pytest.raises(ValueError, match="Count must be greater than 0"):
        round_average_score(50.0, -1)


# --- Task 09D: Decimal Aggregation Unit & Regression Tests ---

from app.core.rounding import sum_decimal, round_sum_scores, round_average_values


def test_round_average_values_001_006():
    """Task 09D Case 1: round_average_values([0.01, 0.06]) == 0.04 (not 0.03)."""
    assert round_average_values([0.01, 0.06]) == 0.04


def test_round_sum_scores_001_006():
    """Task 09D Case 2: round_sum_scores([0.01, 0.06]) == 0.07."""
    assert round_sum_scores([0.01, 0.06]) == 0.07


def test_round_average_values_triplet_half_cent():
    """Task 09D Case 3: A triplet producing exact half-cent rounds up."""
    # [0.02, 0.02, 0.035]: sum = 0.075, avg = 0.075 / 3 = 0.025 -> 0.03
    assert round_average_values([0.02, 0.02, 0.035]) == 0.03
    # [1.0, 1.0, 1.075]: sum = 3.075, avg = 3.075 / 3 = 1.025 -> 1.03
    assert round_average_values([1.0, 1.0, 1.075]) == 1.03


def test_round_average_values_ten_items():
    """Task 09D Case 4: Ten values typical of interview evaluation."""
    scores = [7.5, 8.0, 6.5, 9.0, 7.0, 8.5, 7.25, 6.75, 8.0, 7.75]
    # Exact sum = 76.25, exact avg = 7.625 -> 7.63
    assert round_sum_scores(scores) == 76.25
    assert round_average_values(scores) == 7.63


def test_decimal_aggregation_negative_values():
    """Task 09D Case 5: Negative values handled with ROUND_HALF_UP (half away from zero)."""
    assert round_sum_scores([-0.01, -0.06]) == -0.07
    # -0.07 / 2 = -0.035 -> -0.04
    assert round_average_values([-0.01, -0.06]) == -0.04


def test_decimal_aggregation_nan_rejected():
    """Task 09D Case 6: Iterable containing NaN raises ValueError."""
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        sum_decimal([1.0, float("nan"), 2.0])
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        round_sum_scores([1.0, float("nan"), 2.0])
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        round_average_values([1.0, float("nan"), 2.0])


def test_decimal_aggregation_infinity_rejected():
    """Task 09D Case 7: Iterable containing Infinity raises ValueError."""
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        sum_decimal([1.0, float("inf"), 2.0])
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        round_sum_scores([1.0, float("-inf"), 2.0])
    with pytest.raises(ValueError, match="NaN or Infinity not allowed"):
        round_average_values([1.0, float("inf"), 2.0])


def test_decimal_aggregation_empty_rejected():
    """Task 09D Case 8: Empty iterable raises ValueError."""
    with pytest.raises(ValueError, match="Cannot sum empty sequence"):
        sum_decimal([])
    with pytest.raises(ValueError, match="Cannot sum empty sequence"):
        round_sum_scores([])
    with pytest.raises(ValueError, match="Cannot compute average of empty sequence"):
        round_average_values([])


def test_decimal_aggregation_generator_single_pass():
    """Task 09D Case 9: Generator input is safely consumed in a single pass."""
    def gen_vals():
        yield 0.01
        yield 0.06

    g1 = gen_vals()
    assert round_sum_scores(g1) == 0.07
    # Generator exhausted
    assert list(g1) == []

    g2 = gen_vals()
    assert round_average_values(g2) == 0.04
    assert list(g2) == []


def test_decimal_aggregation_decimal_input():
    """Task 09D Case 10: Decimal inputs preserve exact precision."""
    dec_vals = [Decimal("0.01"), Decimal("0.06")]
    assert sum_decimal(dec_vals) == Decimal("0.07")
    assert round_sum_scores(dec_vals) == 0.07
    assert round_average_values(dec_vals) == 0.04


def test_regression_old_sum_float_vs_new_decimal_aggregation():
    """Task 09D Regression test: proves old implementation failed on float accumulation.

    In binary floating point:
      0.01 + 0.06 = 0.06999999999999999
      0.06999999999999999 / 2 = 0.034999999999999996
    Old implementation converted float_sum to str -> '0.06999999999999999' -> gave 0.03.
    New Decimal aggregation computes Decimal('0.01') + Decimal('0.06') = Decimal('0.07') -> gives 0.04.
    """
    float_sum = sum([0.01, 0.06])
    assert float_sum == 0.06999999999999999

    old_result = round_average_score(float_sum, 2)
    assert old_result == 0.03, "Old implementation produced 0.03 due to float inaccuracy"

    new_result = round_average_values([0.01, 0.06])
    assert new_result == 0.04, "New Decimal aggregation must produce 0.04"

