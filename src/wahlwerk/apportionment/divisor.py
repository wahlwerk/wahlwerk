"""Divisor methods (highest averages): each key's weight is divided by a sequence of
divisors, and the seats go to the largest quotients.

The formula is :func:`wahlwerk_calc.divisor.highest_averages`; a method here names its
signposts (:class:`wahlwerk_calc.divisor.Signposts`), the rounding that tells the
methods apart.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from fractions import Fraction
from typing import Any

from pydantic import Field, field_validator

from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk_calc import divisor as calc
from wahlwerk_calc.result import SeatResult

__all__ = ["DHondt", "DivisorMethod", "LinearDivisor", "SainteLague"]


class DivisorMethod(ApportionmentMethod):
    """Highest averages: seat ``k + 1`` of a key is claimed by its weight over the
    ``k``-th divisor, and the seats go to the largest claims."""

    @property
    @abstractmethod
    def signposts(self) -> calc.Signposts:
        """The method's rounding, as ``wahlwerk_calc`` names it."""

    def calculate(self, weights: Mapping[str, int | Fraction], seats: int) -> SeatResult:
        return calc.highest_averages(weights, seats, self.signposts)


class DHondt(DivisorMethod):
    """D'Hondt (Jefferson): divisors 1, 2, 3, ... Favours larger keys."""

    @property
    def signposts(self) -> calc.Signposts:
        return calc.D_HONDT


class SainteLague(DivisorMethod):
    """Sainte-Laguë/Schepers (Webster): divisors 1, 3, 5, ..., which gives the same
    seats as 0.5, 1.5, 2.5, ..., i.e. standard rounding. Neutral between large and small
    keys; used for the Bundestag."""

    @property
    def signposts(self) -> calc.Signposts:
        return calc.SAINTE_LAGUE


class LinearDivisor(DivisorMethod):
    """Divisors ``first``, ``first + step``, ``first + 2 * step``, ...: D'Hondt is
    ``(1, 1)``, Sainte-Laguë ``(1, 2)``, Imperiali ``(2, 1)``, the Danish method
    ``(1, 3)``."""

    first: Fraction = Field(
        gt=0,
        description="The first divisor; positive, so a key of positive weight has a finite claim.",
    )
    step: Fraction = Field(
        gt=0,
        description="How much each divisor exceeds the one before; positive.",
    )

    @field_validator("first", "step", mode="before")
    @classmethod
    def _no_float(cls, value: Any) -> Any:
        if isinstance(value, float):
            # A ValueError, so pydantic reports it as a ValidationError on the field.
            raise ValueError(f"divisors must be exact (int, Fraction or 'p/q'), got float {value}")  # noqa: TRY004
        return value

    @property
    def signposts(self) -> calc.Signposts:
        return calc.Signposts.from_divisors(self.first, self.step)
