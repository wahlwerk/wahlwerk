r"""Fragmentation: how many keys matter, from their shares :math:`p_i` (of votes or seats).

=========================================  =========================================================
measure                                    formula
=========================================  =========================================================
Herfindahl-Hirschman concentration          :math:`H = \sum_i p_i^2`
Rae fractionalisation                       :math:`F = 1 - H`
effective number (Laakso-Taagepera)         :math:`N = 1 / H`
Golosov                                     :math:`N_G = \sum_i p_i / (p_i + p_1^2 - p_i^2)`, :math:`p_1` the largest
largest share                               :math:`p_1 = \max_i p_i`
=========================================  =========================================================

Votes or seats go in as counts; the shares are taken here
:cite:`Laakso.EffectiveNumberParties.1979,Golosov.EffectiveNumberParties.2010`.

>>> effective_number({"a": 50, "b": 30, "c": 20})
Fraction(50, 19)
>>> effective_number([0.5, 0.3, 0.2])
2.6315789473684212
"""

from __future__ import annotations

from typing import Any

import numpy as np

from wahlwerk.calc._input import Values, div, prepare
from wahlwerk.calc.share import share_array

__all__ = ["effective_number", "fractionalization", "golosov", "herfindahl", "largest_share"]


def herfindahl(values: Values) -> Any:
    r"""Herfindahl-Hirschman: :math:`H = \sum_i p_i^2`; 1 for a single key."""
    return _each(values, lambda p: sum(x * x for x in p))


def fractionalization(values: Values) -> Any:
    r"""Rae: :math:`F = 1 - \sum_i p_i^2`, the chance that two random votes differ."""
    return _each(values, lambda p: 1 - sum(x * x for x in p))


def effective_number(values: Values) -> Any:
    r"""The effective number of parties (Laakso-Taagepera): :math:`N = 1 / \sum_i p_i^2`."""
    return _each(values, lambda p: div(1, sum(x * x for x in p)))


def golosov(values: Values) -> Any:
    r"""Golosov: :math:`N_G = \sum_i p_i / (p_i + p_1^2 - p_i^2)`, less sensitive to the
    largest key than :math:`N`."""
    def index(p: list[Any]) -> Any:
        top = max(p)
        return sum(div(x, x + top * top - x * x) for x in p if x)

    return _each(values, index)


def largest_share(values: Values) -> Any:
    r"""The share of the largest key, :math:`p_1 = \max_i p_i`."""
    return _each(values, max)


def _each(values: Values, index: Any) -> Any:
    prepared = prepare(values)
    p = np.atleast_2d(share_array(prepared))
    out = [index(list(row) if prepared.is_exact else [float(x) for x in row]) for row in p]
    out = [x.numerator if hasattr(x, "denominator") and getattr(x, "denominator", 0) == 1 else x for x in out]
    return prepared.scalar(out)
