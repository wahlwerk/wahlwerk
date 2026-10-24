r"""Shares: each key's part of the whole, the first step of most formulas.

With :math:`v_i` the votes of key :math:`i` and :math:`V = \sum_i v_i`, the vote share is
:math:`p_i = v_i / V`; for seats :math:`s_i` and :math:`S = \sum_i s_i` the seat share is
:math:`q_i = s_i / S`.

>>> shares({"a": 3, "b": 1})
{'a': Fraction(3, 4), 'b': Fraction(1, 4)}
>>> shares([0.3, 0.1])
array([0.75, 0.25])
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from wahlwerk_calc._input import Number, PerKey, Prepared, Values, div, prepare

__all__ = ["share_array", "shares", "total"]


def total(values: Values) -> Any:
    r"""The sum :math:`V = \sum_i v_i`: a number, or one per scenario.

    >>> total({"a": 3, "b": 1})
    4
    """
    prepared = prepare(values)
    return prepared.scalar([sum(row) for row in prepared.rows()])


def shares(values: Values) -> PerKey:
    r"""Each key's share :math:`p_i = v_i / V`; raises ``ValueError`` when :math:`V = 0`."""
    prepared = prepare(values)
    return prepared.wrap(share_array(prepared))


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
