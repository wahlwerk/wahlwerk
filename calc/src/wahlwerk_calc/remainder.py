r"""Largest remainder methods (quota methods): whole seats, then the largest remainders.

Each key first gets the whole part of its votes over the quota :math:`Q`, and the seats
left go one each to the largest remainders:

.. math::

   s_i = \lfloor v_i / Q \rfloor + [\, i \text{ among the } S - \textstyle\sum_j \lfloor v_j/Q \rfloor
   \text{ largest } v_i/Q - \lfloor v_i/Q \rfloor \,]

With the Hare quota this is Hare/Niemeyer (Hamilton) :cite:`Pukelsheim.ProportionalRepresentationApportionment.2017`.

>>> hare_niemeyer({"a": 4160, "b": 3380, "c": 2200}, 10)
SeatResult({'a': 4, 'b': 4, 'c': 2})
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np

from wahlwerk_calc import quota as quotas
from wahlwerk_calc._input import Number, Values, div, prepare
from wahlwerk_calc._select import largest
from wahlwerk_calc.result import SeatResult

__all__ = ["QuotaRule", "hare_niemeyer", "largest_remainder"]

QuotaRule = Callable[[Number, int], Number]
"""A quota as a function of the total votes and the seats, e.g. :func:`wahlwerk_calc.quota.hare`."""


def largest_remainder(
    votes: Values,
    seats: int,
    quota: QuotaRule = quotas.hare,
    *,
    first: str | int | None = None,
) -> SeatResult:
    r"""Apportion ``seats``: :math:`\lfloor v_i/Q \rfloor` each, then the largest remainders.

    ``first`` (a key, or an index for array input), if given, takes one of the seats
    left before any remainder is compared: the majority clause uses it. Raises
    ``ValueError`` if the quota gives more whole seats than there are.
    """
    prepared = prepare(votes)
    index = None
    if first is not None:
        index = prepared.keys.index(first) if prepared.keys is not None and isinstance(first, str) else int(first)
    rows = [_row(row, seats, quota, index) for row in prepared.rows()]
    return SeatResult.from_rows(rows, prepared.keys, prepared.is_batch)


def hare_niemeyer(votes: Values, seats: int) -> SeatResult:
    r"""Hare/Niemeyer (Hamilton): the Hare quota :math:`Q = V/S`, so :math:`v_i/Q = p_i S`."""
    return largest_remainder(votes, seats, quotas.hare)


def _row(row: list[Any], seats: int, quota: QuotaRule, first: int | None) -> tuple[list[int], list[bool], int]:
    n = len(row)
    if isinstance(seats, bool) or not isinstance(seats, (int, np.integer)):
        raise TypeError(f"seats must be an int, got {type(seats).__name__}")
    seats = int(seats)
    if seats < 0:
        raise ValueError(f"seats is negative: {seats}")
    if seats == 0:
        return [0] * n, [False] * n, 0
    whole_votes: Number = sum(row)
    if not whole_votes:
        raise ValueError(f"cannot apportion {seats} seats: every weight is 0")
    q = quota(whole_votes, seats)
    parts = [div(v, q) for v in row]
    whole = [math.floor(p) for p in parts]
    left = seats - sum(whole)
    if left < 0:
        raise ValueError(f"the quota {q} gives {sum(whole)} whole seats, more than the {seats} to apportion")
    if left > n:
        raise ValueError(f"the quota {q} leaves {left} seats for {n} remainders, more than one each")
    ahead = [first] if first is not None and left else []
    rest = [(parts[i] - whole[i], i) for i in range(n) if i not in ahead]
    won, tied, open_seats = largest(rest, left - len(ahead), n)
    for i in ahead:
        won[i] += 1
    return [w + x for w, x in zip(whole, won)], tied, open_seats
