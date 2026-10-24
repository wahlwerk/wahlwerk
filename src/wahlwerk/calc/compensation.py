r"""Überhang and Ausgleich: when options hold more seats than their proportional share.

In mixed systems an option may win more seats outright, in Wahlkreise, than the
apportionment gives it: its Überhang, :math:`\max(0, m_i - s_i)` for a minimum
:math:`m_i`. Ausgleich grows the size :math:`S` until the apportionment covers every
minimum.

>>> overhang({"a": 5, "b": 3}, {"a": 7, "b": 1})
{'a': 2, 'b': 0}
>>> smallest_size({"a": 60, "b": 40}, 10, {"a": 7}).seats
{'a': 7, 'b': 4}
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from wahlwerk.calc._input import PerKey, Values, prepare_pair
from wahlwerk.calc.divisor import sainte_lague
from wahlwerk.calc.result import SeatResult

__all__ = ["SeatRule", "overhang", "raised", "remaining", "smallest_size"]

SeatRule = Callable[[Any, int], SeatResult]
"""A seat formula of votes and seats, e.g. :func:`wahlwerk.calc.divisor.sainte_lague`."""


def overhang(seats: Values, minimum: Values) -> PerKey:
    r"""Each option's Überhang :math:`\max(0, m_i - s_i)`; options missing on one side count 0."""
    s, m = prepare_pair(seats, minimum, names=("seats", "minimum"))
    over = np.maximum(m.values - s.values, 0)
    return s.wrap(over)


def raised(size: int, overhang: Values, factor: int = 1) -> int:
    r"""The size raised for an Überhang: :math:`S + f \sum_i u_i`, ``factor`` seats more
    per seat of Überhang (Sec. 35 (8) LWG LSA: twice).

    >>> raised(83, {"cdu": 6}, factor=2)
    95
    """
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise ValueError(f"size must be a non-negative int, got {size!r}")
    if isinstance(factor, bool) or not isinstance(factor, int) or factor < 0:
        raise ValueError(f"factor must be a non-negative int, got {factor!r}")
    values = list(overhang.values()) if isinstance(overhang, dict) else list(np.asarray(overhang).ravel())
    return size + factor * int(sum(int(v) for v in values))


def remaining(seats: Values, won: Values) -> PerKey:
    r"""The seats left to fill after those won outright, :math:`\max(0, s_i - m_i)`: a
    option's list seats. Options missing on one side count 0.

    >>> remaining({"a": 5, "b": 3}, {"a": 7, "b": 1})
    {'a': 0, 'b': 2}
    """
    s, m = prepare_pair(seats, won, names=("seats", "won"))
    return s.wrap(np.maximum(s.values - m.values, 0))


def smallest_size(
    votes: Values,
    seats: int,
    minimum: Values,
    method: SeatRule = sainte_lague,
    *,
    limit: int | None = None,
) -> SeatResult:
    r"""The apportionment of the smallest size :math:`S' \ge S` in which every option gets
    at least :math:`m_i`: each size is apportioned afresh by ``method``.

    A tie ends the search only if the lot could still cover every minimum; the result
    then carries the tie. Raises ``ValueError`` for a minimum on an option without votes,
    or when ``limit`` is passed.
    """
    v, m = prepare_pair(votes, minimum, names=("votes", "minimum"))
    if v.is_batch:
        raise ValueError("smallest_size takes one scenario")
    row, need = v.rows()[0], [int(x) for x in m.rows()[0]]
    for i, count in enumerate(need):
        if count and not row[i]:
            name = v.options[i] if v.options is not None else i
            raise ValueError(f"no size can give {name!r} its {count} seats: it has no votes")
    size = max(seats, sum(need))
    plain = row if v.options is None else dict(zip(v.options, row))
    while True:
        if limit is not None and size > limit:
            raise ValueError(f"Ausgleich needs more than the limit of {limit} seats")
        result = method(plain, size)
        decided = np.asarray(result.decided)
        if all(decided[i] >= need[i] for i in range(len(need))):
            return result
        if not result.is_decided:
            bonus = result.tie_mask
            if all(decided[i] + bonus[i] >= need[i] for i in range(len(need))):
                return result
        size += 1
