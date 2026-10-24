"""FictitiousParty: a party that did not stand, given a share of the votes.

A core concept: a law that measures something in seats by the seats a party with a
given share of the votes would win (the size of a Fraktion in Sec. 35 (8a) LWG LSA)
imagines such a party. Its votes are ``share`` of a total; the formula is
:func:`wahlwerk.calc.share.counts`, exact, and this names it and its share, so a law
can store and show them. Which total, and among whose votes the party then wins its
seats, is the step's to say.
"""

from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from typing import Any, ClassVar

from pydantic import Field

from wahlwerk.calc import share as calc
from wahlwerk.model import Model, Share

__all__ = ["FictitiousParty"]


class FictitiousParty(Model):
    """A party that did not stand, with ``share`` of the votes."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (calc.counts,)
    """The functions in ``wahlwerk.calc`` it computes with, called through this attribute."""

    share: Share = Field(
        description="Its share of the votes, e.g. ``Fraction(5, 100)``.",
    )

    def votes(self, total: int | Fraction) -> Fraction:
        """Its votes: ``share`` of ``total``, exact."""
        (counts,) = self.formulas
        return Fraction(counts({"fictitious": self.share}, total)["fictitious"])
