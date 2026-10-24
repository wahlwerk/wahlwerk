"""Largest remainder methods (quota methods): each key gets the whole part of its weight
over a quota, and the seats left go to the largest remainders.

The formula is :func:`wahlwerk_calc.remainder.largest_remainder`; a method here names
its quota from :mod:`wahlwerk_calc.quota`.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from fractions import Fraction

from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk_calc import quota as quotas
from wahlwerk_calc import remainder as calc
from wahlwerk_calc.result import SeatResult
from wahlwerk_calc.types import Number

__all__ = ["HareNiemeyer", "LargestRemainder"]


class LargestRemainder(ApportionmentMethod):
    """Quota methods: each key gets the whole part of its weight over the quota, and the
    seats left go to the largest remainders, one each."""

    @abstractmethod
    def quota(self, total: Number, seats: int) -> Number:
        """The weight one seat is worth, given the total weight and the seats."""

    def calculate(self, weights: Mapping[str, int | Fraction], seats: int) -> SeatResult:
        try:
            return calc.largest_remainder(weights, seats, self.quota)
        except ValueError as error:
            raise ValueError(f"{type(self).__name__}: {error}") from None


class HareNiemeyer(LargestRemainder):
    """Hare/Niemeyer (Hamilton): the Hare quota, total weight over seats. So each key's
    share is exactly its weight's proportion of the seats; the whole parts are kept, and
    the largest remainders win the rest."""

    def quota(self, total: Number, seats: int) -> Number:
        return quotas.hare(total, seats)
