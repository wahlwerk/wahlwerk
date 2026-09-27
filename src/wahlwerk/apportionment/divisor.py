"""Divisor methods (highest averages): each key's weight is divided by a sequence of
divisors, and the seats go to the largest quotients."""

from __future__ import annotations

from abc import abstractmethod
from fractions import Fraction
from typing import Any

from pydantic import Field, field_validator

from wahlwerk.apportionment.method import ApportionmentMethod, _largest
from wahlwerk.apportionment.result import Apportionment

__all__ = ["DHondt", "DivisorMethod", "LinearDivisor", "SainteLague"]


class DivisorMethod(ApportionmentMethod):
    """Highest averages: seat ``n`` of a key is claimed by its weight over the ``n``-th
    divisor, and the seats go to the largest claims.

    Divisors must be positive and strictly increasing, so a key's claims strictly
    decrease and it can take part in a tie at most once.
    """

    @abstractmethod
    def divisor(self, index: int) -> Fraction:
        """The divisor for a key's seat number ``index + 1``."""

    def _apportion(self, weights: dict[str, Fraction], seats: int) -> Apportionment:
        claims = [
            (weight / self.divisor(index), key)
            for key, weight in weights.items()
            if weight
            for index in range(seats)
        ]
        winners, tie = _largest(claims, seats)
        return Apportionment(
            seats=tuple((key, winners.count(key)) for key in weights), tie=tie
        )


class DHondt(DivisorMethod):
    """D'Hondt (Jefferson): divisors 1, 2, 3, ... Favours larger keys."""

    def divisor(self, index: int) -> Fraction:
        return Fraction(index + 1)


class SainteLague(DivisorMethod):
    """Sainte-Laguë/Schepers (Webster): divisors 1, 3, 5, ..., which gives the same
    seats as 0.5, 1.5, 2.5, ..., i.e. standard rounding. Neutral between large and small
    keys; used for the Bundestag."""

    def divisor(self, index: int) -> Fraction:
        return Fraction(2 * index + 1)


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

    def divisor(self, index: int) -> Fraction:
        return self.first + index * self.step
