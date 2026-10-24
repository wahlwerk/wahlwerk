r"""Disproportionality: how far seat shares :math:`q_i` stray from vote shares :math:`p_i`.

Each index compares the two over the keys of both sides (a key missing on one side has
0 there) and returns one number per scenario, exact for exact input
:cite:`Gallagher.ProportionalityDisproportionalityElectoral.1991`:

=====================  =================================================================  ==============
index                  formula                                                            proportional
=====================  =================================================================  ==============
Loosemore-Hanby        :math:`\tfrac12 \sum_i |p_i - q_i|`                                0
Rose                   :math:`1 - \mathrm{LH}`                                            1
Gallagher              :math:`\sqrt{\tfrac12 \sum_i (p_i - q_i)^2}`                       0
Rae                    :math:`\tfrac1n \sum_i |p_i - q_i|`                                0
Lijphart               :math:`\max_i |p_i - q_i|`                                         0
Sainte-Laguë           :math:`\sum_i (q_i - p_i)^2 / p_i`                                 0
D'Hondt                :math:`\max_i q_i / p_i`                                           1
regression             :math:`\sum_i p_i q_i / \sum_i p_i^2`                              1
=====================  =================================================================  ==============

The Gallagher index is a square root, so :func:`gallagher_squared` is the exact one and
:func:`gallagher` its float root. :func:`advantage_ratio` is per key.

>>> loosemore_hanby({"a": 68, "b": 22}, {"a": 2})
Fraction(11, 45)
>>> gallagher([0.5, 0.3, 0.2], [0.6, 0.3, 0.1])
0.1
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from wahlwerk_calc._input import Number, PerKey, Values, div, prepare_pair
from wahlwerk_calc.share import share_array

__all__ = [
    "advantage_ratio",
    "d_hondt",
    "gallagher",
    "gallagher_squared",
    "lijphart",
    "loosemore_hanby",
    "rae",
    "regression",
    "rose",
    "sainte_lague",
]


def loosemore_hanby(votes: Values, seats: Values) -> Any:
    r"""Loosemore-Hanby: :math:`\tfrac12 \sum_i |p_i - q_i|`; 0 when proportional, up to 1."""
    return _each(votes, seats, lambda p, q: sum(abs(a - b) for a, b in zip(p, q)) / 2)


def rose(votes: Values, seats: Values) -> Any:
    r"""Rose: :math:`1 - \tfrac12 \sum_i |p_i - q_i|`; 1 when proportional."""
    return _each(votes, seats, lambda p, q: 1 - sum(abs(a - b) for a, b in zip(p, q)) / 2)


def gallagher_squared(votes: Values, seats: Values) -> Any:
    r"""The square of the Gallagher (least squares) index, :math:`\tfrac12 \sum_i (p_i - q_i)^2`;
    exact for exact input."""
    return _each(votes, seats, lambda p, q: sum((a - b) ** 2 for a, b in zip(p, q)) / 2)


def gallagher(votes: Values, seats: Values) -> Any:
    r"""Gallagher (least squares): :math:`\sqrt{\tfrac12 \sum_i (p_i - q_i)^2}`, a float
    :cite:`Gallagher.ProportionalityDisproportionalityElectoral.1991`."""
    squared = gallagher_squared(votes, seats)
    if np.ndim(squared) == 0:
        return round(math.sqrt(squared), 15)
    return np.sqrt(np.asarray(squared, dtype=np.float64))


def rae(votes: Values, seats: Values) -> Any:
    r"""Rae: the mean :math:`\tfrac1n \sum_i |p_i - q_i|` over all :math:`n` keys."""
    return _each(votes, seats, lambda p, q: sum(abs(a - b) for a, b in zip(p, q)) / len(p))


def lijphart(votes: Values, seats: Values) -> Any:
    r"""Lijphart: the largest deviation :math:`\max_i |p_i - q_i|`."""
    return _each(votes, seats, lambda p, q: max(abs(a - b) for a, b in zip(p, q)))


def sainte_lague(votes: Values, seats: Values) -> Any:
    r"""Sainte-Laguë: :math:`\sum_i (q_i - p_i)^2 / p_i`, the index the Sainte-Laguë method
    minimises. Raises ``ValueError`` if a key without votes won seats (infinite)."""
    return _each(votes, seats, lambda p, q: sum(_over(b, a, (a - b) ** 2) for a, b in zip(p, q)))


def d_hondt(votes: Values, seats: Values) -> Any:
    r"""D'Hondt: :math:`\max_i q_i / p_i`, the index the D'Hondt method minimises; 1 when
    proportional. Raises ``ValueError`` if a key without votes won seats (infinite)."""
    return _each(votes, seats, lambda p, q: max(_over(b, a, b) for a, b in zip(p, q)))


def regression(votes: Values, seats: Values) -> Any:
    r"""The regression index :math:`\sum_i p_i q_i / \sum_i p_i^2`, the slope of seat
    shares on vote shares through the origin: above 1 favours large keys."""
    return _each(
        votes, seats, lambda p, q: div(sum(a * b for a, b in zip(p, q)), sum(a * a for a in p))
    )


def advantage_ratio(votes: Values, seats: Values) -> PerKey:
    r"""Per key, :math:`q_i / p_i`: above 1 a key holds more seats than votes. A key
    without votes and without seats has 0; without votes but with seats, infinity
    (``ValueError`` for exact input)."""
    v, s = prepare_pair(votes, seats)
    p, q = share_array(v), share_array(s)
    exact = v.is_exact and s.is_exact
    ratios = [
        _over(qi, pi, qi, allow_infinite=not exact)
        for pi, qi in zip(p.ravel().tolist(), q.ravel().tolist())
    ]
    out = np.empty(p.shape, dtype=object if exact else np.float64)
    out.ravel()[:] = ratios
    return v.wrap(out)


def _each(votes: Values, seats: Values, index: Any) -> Any:
    v, s = prepare_pair(votes, seats)
    p, q = share_array(v), share_array(s)
    exact = v.is_exact and s.is_exact
    p2: NDArray[Any] = np.atleast_2d(p)
    q2: NDArray[Any] = np.atleast_2d(q)
    values = []
    for prow, qrow in zip(p2, q2):
        a, b = list(prow), list(qrow)
        if not exact:
            a, b = [float(x) for x in a], [float(x) for x in b]
        values.append(_plain(index(a, b)))
    if v.is_batch:
        return np.asarray(values, dtype=object if exact else np.float64)
    return values[0]


def _over(seat_share: Number, vote_share: Number, value: Number, *, allow_infinite: bool = False) -> Number:
    """``value / vote_share``, 0 for a key with neither votes nor seats."""
    if vote_share:
        return div(value, vote_share)
    if seat_share:
        if allow_infinite:
            return math.inf
        raise ValueError("a key without votes won seats: the index is infinite")
    return 0


def _plain(value: Any) -> Any:
    from fractions import Fraction

    if isinstance(value, Fraction) and value.denominator == 1:
        return value.numerator
    return value
