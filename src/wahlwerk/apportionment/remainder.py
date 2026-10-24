"""Largest remainder methods (quota methods): each option gets the whole part of its weight
over a quota, and the seats left go to the largest remainders.

The formula is :func:`wahlwerk.calc.remainder.largest_remainder`; a method here names
its quota from :mod:`wahlwerk.calc.quota`.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Mapping
from fractions import Fraction
from typing import Any, ClassVar

from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk.calc import quota as quotas
from wahlwerk.calc import remainder as calc
from wahlwerk.calc.result import SeatResult
from wahlwerk.calc.types import Number

__all__ = ["HareNiemeyer", "LargestRemainder"]


class LargestRemainder(ApportionmentMethod):
    """Quota methods: each option gets the whole part of its weight over the quota, and the
    seats left go to the largest remainders, one each."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (calc.largest_remainder,)
    """The remainder formula first; a family adds the quota it divides by."""

    @abstractmethod
    def quota(self, total: Number, seats: int) -> Number:
        """The weight one seat is worth, given the total weight and the seats."""

    def calculate(self, weights: Mapping[str, int | Fraction], seats: int) -> SeatResult:
        try:
            result: SeatResult = self.formulas[0](weights, seats, self.quota)
            return result
        except ValueError as error:
            raise ValueError(f"{type(self).__name__}: {error}") from None


class HareNiemeyer(LargestRemainder):
    """Hare/Niemeyer (Hamilton): the Hare quota, total weight over seats. So each option's
    share is exactly its weight's proportion of the seats; the whole parts are kept, and
    the largest remainders win the rest."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (calc.largest_remainder, quotas.hare)

    def quota(self, total: Number, seats: int) -> Number:
        hare: Callable[[Number, int], Number] = self.formulas[1]
        return hare(total, seats)
