r"""Shares: each key's part of the whole, the first step of most formulas.

With :math:`v_i` the votes of key :math:`i` and :math:`V = \sum_i v_i`, the vote share is
:math:`p_i = v_i / V`; for seats :math:`s_i` and :math:`S = \sum_i s_i` the seat share is
:math:`q_i = s_i / S`.

Both directions, with ``per`` for the unit of a share (1 for fractions, 100 for
percent): :func:`shares` takes counts to shares, :func:`counts` shares back to counts of a
given total, always exactly.

>>> shares({"a": 3, "b": 1})
{'a': Fraction(3, 4), 'b': Fraction(1, 4)}
>>> shares([3.0, 1.0], per=100)
array([75., 25.])
>>> counts({"a": 32.5, "b": 67.5}, 1000, per=100)
{'a': 325, 'b': 675}
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import numpy as np
from numpy.typing import NDArray

from wahlwerk.calc._input import (
    Number,
    PerKey,
    Prepared,
    Values,
    div,
    prepare,
    to_number,
)

__all__ = ["counts", "share_array", "shares", "total"]


def total(values: Values) -> Any:
    r"""The sum :math:`V = \sum_i v_i`: a number, or one per scenario.

    >>> total({"a": 3, "b": 1})
    4
    """
    prepared = prepare(values)
    return prepared.scalar([sum(row) for row in prepared.rows()])


def shares(values: Values, *, per: Number | str = 1) -> PerKey:
    r"""Each key's share of the total, :math:`p_i = v_i / V`, in units of ``per``
    (``per=100`` for percent): exact for exact input, floats for floats. Raises
    ``ValueError`` when :math:`V = 0`."""
    prepared = prepare(values)
    scale = to_number(per, name="per")
    if scale <= 0:
        raise ValueError(f"per must be positive, got {scale}")
    array = share_array(prepared)
    return prepared.wrap(array if scale == 1 else array * scale)


def counts(shares: Values, total: Any, *, per: Number | str = 1) -> PerKey:
    r"""The absolute counts of shares of a given total, :math:`v_i = p_i V`; with the
    shares in units of ``per`` (``per=100`` for percent), :math:`v_i = p_i V /` ``per``.

    **Always exact**: a float share is read as the decimal it prints, so ``32.5`` percent
    of 1000 is exactly 325, never 324.99999999999994. A count that is not whole stays a
    ``Fraction``; for whole counts that add up to the total, apportion the total by the
    shares with :func:`wahlwerk.calc.remainder.hare_niemeyer`. ``total`` is one number,
    or one per scenario for 2-D shares. The shares need not add up to ``per``.

    >>> counts([0.1, 0.2], 3).tolist()
    [Fraction(3, 10), Fraction(3, 5)]
    >>> counts({"a": "1/3", "b": "2/3"}, 300)
    {'a': 100, 'b': 200}
    """
    prepared = prepare(shares, name="shares")
    scale = _decimal(to_number(per, name="per"))
    if scale <= 0:
        raise ValueError(f"per must be positive, got {scale}")
    rows = prepared.rows()
    if np.ndim(total) == 0:
        totals = [total] * len(rows)
    else:
        totals = list(np.asarray(total, dtype=object).tolist())
        if len(totals) != len(rows):
            raise ValueError(f"one total per scenario: {len(rows)} rows, {len(totals)} totals")
    out = []
    for row, whole in zip(rows, totals):
        v = _decimal(to_number(whole, name="total"))
        if v < 0:
            raise ValueError(f"total must not be negative, got {v}")
        parts = [_decimal(x) for x in row]
        too_big = [p for p in parts if p > scale]
        if too_big:
            raise ValueError(f"a share above {scale}: {too_big[0]}")
        out.append([_whole(p * v / scale) for p in parts])
    array = np.empty((len(out), len(out[0]) if out else 0), dtype=object)
    for i, values in enumerate(out):
        array[i, :] = values
    return prepared.wrap(array if prepared.is_batch else array[0])


def _decimal(value: Number) -> Fraction:
    """A number exactly, a float as the shortest decimal that prints it (0.1 is 1/10)."""
    if isinstance(value, (float, np.floating)):
        return Fraction(repr(float(value)))
    return Fraction(value)


def _whole(value: Fraction) -> Number:
    return value.numerator if value.denominator == 1 else value


def share_array(prepared: Prepared) -> NDArray[Any]:
    """The shares of checked input, keys on the last axis (exact or float)."""
    out = []
    for row in prepared.rows():
        whole: Number = sum(row)
        if not whole:
            raise ValueError("shares of nothing: every value is 0")
        out.append([div(x, whole) for x in row])
    array = np.empty((len(out), len(out[0]) if out else 0), dtype=object if prepared.is_exact else np.float64)
    for i, row_values in enumerate(out):
        array[i, :] = row_values
    return array if prepared.is_batch else array[0]
