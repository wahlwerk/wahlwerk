r"""Plurality: the options with the most votes win, one seat each.

With one seat this is first past the post, the rule of a Wahlkreis: the option with the
most votes wins, :math:`\arg\max_i v_i`, and equal tops are a tie. With :math:`S` seats
it is the single non-transferable vote: the :math:`S` options with the most votes.

>>> plurality({"a": 120, "b": 95, "c": 120})
SeatResult({'a': 0, 'b': 0, 'c': 0}, tied=['a', 'c'], open=1)
>>> plurality([120, 95, 80]).seats
array([1, 0, 0])
"""

from __future__ import annotations

from wahlwerk.calc._input import Values, prepare
from wahlwerk.calc._select import largest
from wahlwerk.calc.result import SeatResult

__all__ = ["plurality"]


def plurality(votes: Values, seats: int = 1) -> SeatResult:
    r"""The ``seats`` options with the most votes, one seat each; an option without votes wins
    nothing. Raises ``ValueError`` for more seats than options with votes."""
    prepared = prepare(votes)
    rows = []
    for row in prepared.rows():
        claims = [(v, i) for i, v in enumerate(row) if v]
        if seats > len(claims):
            raise ValueError(f"{seats} seats for {len(claims)} options with votes")
        rows.append(largest(claims, seats, len(row)))
    return SeatResult.from_rows(rows, prepared.options, prepared.is_batch)
