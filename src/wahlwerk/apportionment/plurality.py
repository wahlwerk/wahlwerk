"""Plurality, or relative majority: the key with the most weight takes the seat.

The simplest way to choose: take a list of keys and their votes, and the one with the
most wins, whether or not it has more than half (that would be an absolute majority).
Winner takes all. Nothing in it is about a Wahlkreis, a party or a person: the same
method elects the member of a single-seat unit, could fill an office, or decide between
options, wherever a law says "the most votes win". Equal tops are a
:class:`~wahlwerk.apportionment.tie.Tie`, left to the lot the law prescribes.

The formula is :func:`wahlwerk.calc.plurality.plurality`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from fractions import Fraction
from typing import ClassVar

from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk.calc import plurality as calc
from wahlwerk.calc.result import SeatResult

__all__ = ["Plurality"]


class Plurality(ApportionmentMethod):
    """The keys with the most weight win, one seat each; with one seat, the key with
    the most weight wins it (first past the post). A key of weight 0 wins nothing."""

    formula: ClassVar[Callable[..., SeatResult]] = staticmethod(calc.plurality)

    def calculate(self, weights: Mapping[str, int | Fraction], seats: int) -> SeatResult:
        return self.formula(weights, seats)
