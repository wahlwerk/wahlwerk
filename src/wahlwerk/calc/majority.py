r"""Majorities: how many are needed, and the clause that secures one.

With :math:`M` members (or votes cast, whichever the rule counts), a majority of
:math:`M` is more than half,

.. math::

   \operatorname{maj}(M) = \lfloor M / 2 \rfloor + 1,

and a qualified majority of a share :math:`r` (two thirds, say) is at least that share,
:math:`\lceil r M \rceil`, or more than it, :math:`\lfloor r M \rfloor + 1`.

>>> majority_of(598), qualified_majority(630, "2/3")
(300, 420)
>>> majority_of([69, 71, 79])
array([35, 36, 40])
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

import numpy as np

from wahlwerk.calc import quota as quotas
from wahlwerk.calc._input import Number, Values, prepare, to_number
from wahlwerk.calc.remainder import QuotaRule, largest_remainder
from wahlwerk.calc.result import SeatResult

__all__ = ["is_majority", "majority_first", "majority_of", "qualified_majority"]


def majority_of(members: Any) -> Any:
    r"""The smallest number above half: :math:`\lfloor M/2 \rfloor + 1`. An ``int``, or
    an array for an array of member counts."""
    return qualified_majority(members, Fraction(1, 2), is_strict=True)


def qualified_majority(members: Any, share: Number | str, *, is_strict: bool = False) -> Any:
    r"""The smallest whole number that is at least ``share`` of :math:`M`,
    :math:`\lceil r M \rceil`; with ``is_strict``, more than it,
    :math:`\lfloor r M \rfloor + 1`."""
    r = Fraction(to_number(share, name="share"))
    if not 0 < r <= 1:
        raise ValueError(f"share must be in (0, 1], got {r}")

    def one(m: Any) -> int:
        count = int(m)
        if count < 0:
            raise ValueError(f"members must not be negative, got {count}")
        return int(math.floor(r * count) + 1 if is_strict else math.ceil(r * count))

    if np.ndim(members) == 0:
        return one(members)
    return np.vectorize(one, otypes=[np.int64])(np.asarray(members))


def is_majority(yes: Any, base: Any, share: Number | str = Fraction(1, 2), *, is_strict: bool = True) -> Any:
    r"""Whether ``yes`` reaches the majority of ``base``: more than ``share`` of it
    (``is_strict``), or at least that share. Vectorised over arrays."""
    r = Fraction(to_number(share, name="share"))
    y, b = np.asarray(yes, dtype=object), np.asarray(base, dtype=object)
    result = (y > b * r) if is_strict else (y >= b * r)
    return bool(result) if np.ndim(result) == 0 else np.asarray(result, dtype=bool)


def majority_first(votes: Values, seats: int, quota: QuotaRule = quotas.hare) -> SeatResult:
    r"""Largest remainder with a majority clause: a key with more than half the votes,
    left with no more than half the seats, takes one of the remainder seats first
    (e.g. Sec. 35 (6) LWG LSA). The total stays :math:`S`.

    >>> majority_first({"a": 501, "b": 499}, 2).seats
    {'a': 2, 'b': 0}
    """
    prepared = prepare(votes)
    plain = largest_remainder(votes, seats, quota)
    if prepared.is_batch:
        raise ValueError("majority_first takes one scenario")
    row = prepared.rows()[0]
    whole: Number = sum(row)
    leader = next((i for i, v in enumerate(row) if 2 * v > whole), None)
    if leader is None or 2 * int(plain.decided[leader]) > seats:
        return plain
    return largest_remainder(votes, seats, quota, first=leader)
