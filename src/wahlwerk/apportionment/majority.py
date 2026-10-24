"""Majority clauses: rules that adjust an apportionment so an option with a majority of the
weight gets a majority of the seats."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from fractions import Fraction
from typing import Any, ClassVar

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk.apportionment.remainder import LargestRemainder
from wahlwerk.calc import majority as calc
from wahlwerk.calc.result import SeatResult

__all__ = ["MajorityFirst"]


class MajorityFirst(ApportionmentMethod):
    """A largest remainder method where an option with more than half the weight, left with
    no more than half the seats, takes one of the remainder seats first.

    This is the majority clause of Sec. 35 (6) LWG LSA: the other remainder seats then
    go by the method as usual, and the total stays the same. When the clause applies,
    the option cannot have won a remainder seat already, so the seat it takes first always
    gives it a majority. The formula is :func:`wahlwerk.calc.majority.majority_first`.
    """

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (calc.majority_first,)

    method: SerializeAsAny[LargestRemainder] = Field(
        description="The largest remainder method the clause adjusts, e.g. ``HareNiemeyer()``.",
    )

    def calculate(self, weights: Mapping[str, int | Fraction], seats: int) -> SeatResult:
        (majority_first,) = self.formulas
        result: SeatResult = majority_first(weights, seats, self.method.quota)
        return result
