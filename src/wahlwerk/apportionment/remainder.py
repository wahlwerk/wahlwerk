"""Largest remainder methods (quota methods): each key gets the whole part of its weight
over a quota, and the seats left go to the largest remainders.

The formula is :func:`wahlwerk.calc.remainder.largest_remainder`; a method here names
its quota from :mod:`wahlwerk.calc.quota`.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Mapping
from fractions import Fraction
from typing import ClassVar

from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk.calc import quota as quotas
from wahlwerk.calc import remainder as calc
from wahlwerk.calc.result import SeatResult
from wahlwerk.calc.types import Number

__all__ = ["HareNiemeyer", "LargestRemainder"]


class LargestRemainder(ApportionmentMethod):
    """Quota methods: each key gets the whole part of its weight over the quota, and the
    seats left go to the largest remainders, one each."""

    formula: ClassVar[Callable[..., SeatResult]] = staticmethod(calc.largest_remainder)

    @abstractmethod
    def quota(self, total: Number, seats: int) -> Number:
        """The weight one seat is worth, given the total weight and the seats."""

    def calculate(self, weights: Mapping[str, int | Fraction], seats: int) -> SeatResult:
        try:
            return self.formula(weights, seats, self.quota)
        except ValueError as error:
            raise ValueError(f"{type(self).__name__}: {error}") from None


class HareNiemeyer(LargestRemainder):
    """Hare/Niemeyer (Hamilton): the Hare quota, total weight over seats. So each key's
    share is exactly its weight's proportion of the seats; the whole parts are kept, and
    the largest remainders win the rest."""

    def quota(self, total: Number, seats: int) -> Number:
        return quotas.hare(total, seats)
