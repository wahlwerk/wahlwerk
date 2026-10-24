"""Quotas: how many votes one seat is worth.

A quota is a core concept of its own: given the votes counted and the seats to fill, it
says what one seat costs. Whole seats are then whole multiples of it. The formulas are
in :mod:`wahlwerk.calc.quota`; a quota here names one, so a law can store and show it.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from fractions import Fraction
from typing import Any, ClassVar

from wahlwerk.calc import quota as calc
from wahlwerk.model import Model

__all__ = ["HareQuota", "Quota"]


class Quota(Model):
    """The votes one seat is worth, for some total of votes and seats."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = ()
    """The functions in ``wahlwerk.calc`` it computes with, called through this attribute."""

    @abstractmethod
    def of(self, votes: int | Fraction, seats: int) -> Fraction:
        """The quota for ``votes`` counted and ``seats`` to fill."""


class HareQuota(Quota):
    """The Hare quota: the votes counted over the seats, so a key with exactly that many
    votes is worth exactly one seat."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (calc.hare,)

    def of(self, votes: int | Fraction, seats: int) -> Fraction:
        (hare,) = self.formulas
        return Fraction(hare(votes, seats))
