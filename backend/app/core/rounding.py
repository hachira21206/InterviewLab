"""Centralized scoring and rounding contract utilities using ROUND_HALF_UP.

This module guarantees consistent mathematical rounding between Python backend
and JavaScript frontend across all evaluation and progress metrics.
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import math
from typing import Union, Iterable

TWO_PLACES = Decimal("0.01")


def to_decimal(value: Union[float, int, str, Decimal]) -> Decimal:
    """Safely convert a numeric or string value to Decimal.

    Rejects NaN, Infinity, and invalid string representations by raising ValueError.
    """
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"Invalid numeric value: {value} (NaN or Infinity not allowed)")
        # Convert float to str to avoid binary floating-point representation artifacts
        return Decimal(str(value))
    elif isinstance(value, Decimal):
        if value.is_nan() or value.is_infinite():
            raise ValueError(f"Invalid Decimal value: {value} (NaN or Infinity not allowed)")
        return value
    elif isinstance(value, int):
        return Decimal(value)
    elif isinstance(value, str):
        try:
            d = Decimal(value.strip())
            if d.is_nan() or d.is_infinite():
                raise ValueError(f"Invalid string decimal: {value} (NaN or Infinity not allowed)")
            return d
        except InvalidOperation as exc:
            raise ValueError(f"Cannot parse decimal from string: {value}") from exc
    else:
        raise ValueError(f"Unsupported type for decimal conversion: {type(value)}")


def round_half_up_decimal(value: Union[float, int, str, Decimal], places: int = 2) -> Decimal:
    """Round a numeric value to specified decimal places using ROUND_HALF_UP semantics.

    Preserves exact Decimal precision without premature float conversion.
    """
    d = to_decimal(value)
    target = Decimal("10") ** (-places)
    return d.quantize(target, rounding=ROUND_HALF_UP)


def round_score(value: Union[float, int, str, Decimal]) -> float:
    """Round a score to 2 decimal places using ROUND_HALF_UP, serialized to float at boundary."""
    return float(round_half_up_decimal(value, 2))


def round_average_score(total: Union[float, int, str, Decimal], count: int = 10) -> float:
    """Compute average score (total / count) and round to 2 decimal places using ROUND_HALF_UP.

    Division is performed strictly in Decimal space before quantizing.
    """
    if count <= 0:
        raise ValueError("Count must be greater than 0")
    d_total = to_decimal(total)
    d_count = Decimal(count)
    d_avg = d_total / d_count
    return float(d_avg.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def round_delta(
    current: Union[float, int, str, Decimal],
    base: Union[float, int, str, Decimal],
) -> float:
    """Compute delta (current - base) and round to 2 decimal places using ROUND_HALF_UP.

    Subtraction is performed strictly in Decimal space before quantizing.
    """
    d_cur = to_decimal(current)
    d_base = to_decimal(base)
    d_diff = d_cur - d_base
    return float(d_diff.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def sum_decimal(values: Iterable[Union[float, int, str, Decimal]]) -> Decimal:
    """Safely sum an iterable of values strictly in Decimal space without float accumulation.

    Rejects empty sequences, NaN, and Infinity. Supports single-pass generator iteration.
    """
    total = Decimal("0")
    has_any = False
    for v in values:
        has_any = True
        total += to_decimal(v)
    if not has_any:
        raise ValueError("Cannot sum empty sequence")
    return total


def round_sum_scores(values: Iterable[Union[float, int, str, Decimal]]) -> float:
    """Sum values in Decimal space and round to 2 decimal places using ROUND_HALF_UP.

    Serialized to float strictly at the boundary.
    """
    d_sum = sum_decimal(values)
    return float(d_sum.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def round_average_values(values: Iterable[Union[float, int, str, Decimal]]) -> float:
    """Compute average (sum(values) / len(values)) strictly in Decimal space.

    Converts each operand to Decimal before addition, performs Decimal division,
    and quantizes using ROUND_HALF_UP. Safely handles single-pass generators.
    """
    total = Decimal("0")
    count = 0
    for v in values:
        total += to_decimal(v)
        count += 1
    if count == 0:
        raise ValueError("Cannot compute average of empty sequence")
    d_avg = total / Decimal(count)
    return float(d_avg.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))

