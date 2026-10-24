r"""Thresholds: which keys take part at all.

Each returns, per key, whether it passes: a ``dict`` of booleans for keyed input, a
boolean array otherwise. A legal threshold of a share :math:`\theta` (five percent)
passes key :math:`i` when :math:`p_i \ge \theta`, i.e. :math:`v_i \ge \theta V`; a
Grundmandatsklausel passes keys that won at least so many seats outright. Combine
masks with ``|`` (numpy) or ``or``.

>>> share_threshold({"a": 60, "b": 36, "c": 4}, "5/100")
{'a': True, 'b': True, 'c': False}
"""

from __future__ import annotations

from fractions import Fraction
from typing import Any

import numpy as np

from wahlwerk.calc._input import Number, PerKey, Values, div, prepare, to_number

__all__ = ["count_threshold", "effective_threshold", "seat_threshold", "share_threshold"]


def share_threshold(votes: Values, share: Number | str, *, accept_equal: bool = True) -> PerKey:
    r"""Passes keys with :math:`v_i \ge \theta V` ("mindestens"), or :math:`v_i > \theta V`
    without ``accept_equal`` ("mehr als")."""
    theta = to_number(share, name="share")
    if not 0 <= theta <= 1:
        raise ValueError(f"share must be in [0, 1], got {theta}")
    prepared = prepare(votes)
    out = []
    for row in prepared.rows():
        needed = sum(row) * (theta if isinstance(theta, float) else Fraction(theta))
        out.append([v > needed or (accept_equal and v == needed) for v in row])
    return prepared.wrap(np.asarray(out if prepared.is_batch else out[0], dtype=bool))


def count_threshold(votes: Values, count: Number | str, *, accept_equal: bool = True) -> PerKey:
    r"""Passes keys with :math:`v_i \ge` ``count`` (or :math:`>` without ``accept_equal``)."""
    needed = to_number(count, name="count")
    prepared = prepare(votes)
    values = prepared.values
    mask = (values >= needed) if accept_equal else (values > needed)
    return prepared.wrap(np.asarray(mask, dtype=bool))


def seat_threshold(won: Values, seats: int) -> PerKey:
    r"""Passes keys that already won at least ``seats`` seats (the Grundmandatsklausel:
    three Wahlkreise)."""
    prepared = prepare(won, name="won", is_integer=True)
    return prepared.wrap(np.asarray(prepared.values >= seats, dtype=bool))


def effective_threshold(magnitude: Any) -> Any:
    r"""Taagepera's effective threshold of a district of magnitude :math:`m`:
    :math:`T_{\text{eff}} = \tfrac{3}{4} / (m + 1)`, the vote share at which a key
    tends to win its first seat :cite:`Taagepera.NationwideThresholdRepresentation.2002`.

    >>> effective_threshold(9)
    Fraction(3, 40)
    """
    def one(m: Any) -> Number:
        return div(Fraction(3, 4), to_number(m, name="magnitude") + 1)

    if np.ndim(magnitude) == 0:
        return one(magnitude)
    return np.asarray([one(m) for m in np.asarray(magnitude).tolist()], dtype=object)
