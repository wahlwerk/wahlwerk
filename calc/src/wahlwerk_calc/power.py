r"""Power indices: how often a key decides, in a weighted vote with quota :math:`T`.

Key :math:`i` is **pivotal** (a swing) for a coalition :math:`C \not\ni i` when
:math:`w(C) < T \le w(C) + s_i`. With :math:`\eta_i` the number of such coalitions and
:math:`n` keys:

- Banzhaf :cite:`Banzhaf.WeightedVotingDoesnt.1965`, normalised:
  :math:`\beta_i = \eta_i / \sum_j \eta_j`; absolute (Penrose):
  :math:`\beta'_i = \eta_i / 2^{n-1}`.
- Shapley-Shubik :cite:`Shapley.MethodEvaluatingDistribution.1954`: the share of the
  :math:`n!` orders in which :math:`i` is pivotal,
  :math:`\phi_i = \sum_{C \not\ni i \text{ swing}} |C|!\,(n-|C|-1)!/n!`.

Weights must be whole (seats); the results are exact fractions, counted by dynamic
programming over the weights, not by listing coalitions.

>>> banzhaf({"a": 50, "b": 49, "c": 1})
{'a': Fraction(3, 5), 'b': Fraction(1, 5), 'c': Fraction(1, 5)}
>>> shapley_shubik([3, 2, 1, 1], quota=4).tolist()
[Fraction(1, 2), Fraction(1, 6), Fraction(1, 6), Fraction(1, 6)]
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Any

import numpy as np

from wahlwerk_calc._input import Number, PerKey, Values, prepare, to_number
from wahlwerk_calc.majority import majority_of

__all__ = ["banzhaf", "penrose", "shapley_shubik", "swings"]


def swings(seats: Values, quota: Number | str | None = None) -> PerKey:
    r""":math:`\eta_i`, the coalitions for which key :math:`i` is pivotal."""
    return _per_key(seats, quota, lambda s, t: _swings(s, t))


def banzhaf(seats: Values, quota: Number | str | None = None) -> PerKey:
    r"""The normalised Banzhaf index :math:`\beta_i = \eta_i / \sum_j \eta_j`."""
    def index(s: list[int], t: int) -> list[Any]:
        eta = _swings(s, t)
        whole = sum(eta)
        return [Fraction(e, whole) if whole else Fraction(0) for e in eta]

    return _per_key(seats, quota, index)


def penrose(seats: Values, quota: Number | str | None = None) -> PerKey:
    r"""The absolute Banzhaf (Penrose) index :math:`\beta'_i = \eta_i / 2^{n-1}`."""
    return _per_key(seats, quota, lambda s, t: [Fraction(e, 2 ** (len(s) - 1)) for e in _swings(s, t)])


def shapley_shubik(seats: Values, quota: Number | str | None = None) -> PerKey:
    r"""The Shapley-Shubik index :math:`\phi_i`."""
    def index(s: list[int], t: int) -> list[Any]:
        n = len(s)
        out = []
        for i in range(n):
            others = s[:i] + s[i + 1 :]
            counts = _sums_by_size(others, t)
            total = Fraction(0)
            for size, by_weight in enumerate(counts):
                pivots = sum(by_weight[w] for w in range(max(0, t - s[i]), t))
                if pivots:
                    total += Fraction(pivots * math.factorial(size) * math.factorial(n - size - 1), math.factorial(n))
            out.append(total)
        return out

    return _per_key(seats, quota, index)


def _per_key(seats: Values, quota: Number | str | None, index: Any) -> PerKey:
    prepared = prepare(seats, name="seats", is_integer=True)
    out = []
    for row in prepared.rows():
        s = [int(x) for x in row]
        t = majority_of(sum(s)) if quota is None else math.ceil(to_number(quota, name="quota"))
        out.append(index(s, t))
    array = np.empty((len(out), len(out[0])), dtype=object)
    for r, values in enumerate(out):
        array[r, :] = values
    result = array if prepared.is_batch else array[0]
    return prepared.wrap(result)


def _swings(s: list[int], t: int) -> list[int]:
    eta = []
    for i in range(len(s)):
        counts = _sums(s[:i] + s[i + 1 :], t)
        eta.append(sum(counts[w] for w in range(max(0, t - s[i]), t)))
    return eta


def _sums(weights: list[int], cap: int) -> list[int]:
    """How many subsets of ``weights`` weigh exactly ``w``, for ``w < cap``."""
    counts = [0] * max(cap, 1)
    counts[0] = 1
    for x in weights:
        for w in range(len(counts) - 1, x - 1, -1):
            counts[w] += counts[w - x]
    return counts


def _sums_by_size(weights: list[int], cap: int) -> list[list[int]]:
    """``[size][w]``: subsets of a given size weighing exactly ``w < cap``."""
    n = len(weights)
    counts = [[0] * max(cap, 1) for _ in range(n + 1)]
    counts[0][0] = 1
    for x in weights:
        for size in range(n, 0, -1):
            below, here = counts[size - 1], counts[size]
            for w in range(len(here) - 1, x - 1, -1):
                here[w] += below[w - x]
    return counts
