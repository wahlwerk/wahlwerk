"""Eligibility: which parties take part in the proportional allocation, and how many
seats it divides (e.g. Sec. 1 (1) and 35 (3), (4) LWG LSA)."""

from __future__ import annotations

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.threshold import Threshold
from wahlwerk.ids import LevelName, Slug
from wahlwerk.model import Seats
from wahlwerk.process.allocation.base import Allocation, AllocationStep, total_fact

__all__ = ["ApplyThreshold", "SetChamberSize", "SetSeatTotal"]


class ApplyThreshold(AllocationStep):
    """The parties that pass ``threshold`` on their valid votes in ``section``, summed
    at ``level``, become ``eligible``.

    The share is of all valid votes in the section, of every party. A threshold that
    counts seats already won (a Grundmandatsklausel) is given each party's Wahlkreis
    wins, so the step then also reads ``unit_winners``.
    """

    threshold: SerializeAsAny[Threshold] = Field(
        description="The threshold, e.g. ``RelativeThreshold(share='5/100')``.",
    )
    section: Slug = Field(
        description="The vote the threshold is measured on, e.g. ``zweitstimme``.",
    )
    level: LevelName = Field(
        description="The level it is measured at, e.g. ``land``.",
    )

    @property
    def reads(self) -> frozenset[str]:
        needed = {total_fact(self.level)}
        if self.threshold.uses_won:
            needed.add("unit_winners")
        return frozenset(needed)

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"eligible"})

    def _apply(self, allocation: Allocation) -> Allocation:
        votes = allocation.votes_by_party(self.level, self.section)
        won = allocation.unit_wins() if self.threshold.uses_won else None
        return allocation.with_values(eligible=self.threshold.select(votes, won))


class SetChamberSize(AllocationStep):
    """The chamber has ``seats`` seats to begin with, e.g. 83 (Sec. 1 (1) LWG LSA); a
    Mehrsitze or Ausgleich rule may raise the size later.

    Where the law says "at least" ("mindestens 83"), the same number is the chamber's
    minimum (``is_minimum``), which stays when the size is raised: one number in the law,
    written once here. A law whose minimum differs from its size sets ``is_minimum`` false
    and gives the minimum to :class:`~wahlwerk.process.allocation.chamber.FormChamber`.
    """

    seats: Seats = Field(
        description="The seats of the chamber before any Mehrsitze or Ausgleich, e.g. 83.",
    )
    is_minimum: bool = Field(
        default=True,
        description="Whether the chamber also has at least these seats by law, as \"mindestens 83\" says.",
    )

    @property
    def reads(self) -> frozenset[str]:
        return frozenset({"tally"})

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"chamber_size", "minimum_mandates"} if self.is_minimum else {"chamber_size"})

    def _apply(self, allocation: Allocation) -> Allocation:
        if self.is_minimum:
            return allocation.with_values(chamber_size=self.seats, minimum_mandates=self.seats)
        return allocation.with_values(chamber_size=self.seats)


class SetSeatTotal(AllocationStep):
    """The seats the proportional allocation divides: the ``chamber_size`` less the Wahlkreis
    seats of winners who take no part in it, i.e. Einzelbewerber and parties that are
    not ``eligible``.

    Their seats are theirs regardless; the rest of the chamber size is divided among the
    eligible parties, whose own Wahlkreis seats are deducted later.
    """

    @property
    def reads(self) -> frozenset[str]:
        return frozenset({"chamber_size", "unit_winners", "eligible"})

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"seat_total"})

    def _apply(self, allocation: Allocation) -> Allocation:
        wins = allocation.unit_wins()
        eligible = allocation.eligible or frozenset()
        winners = allocation.unit_winners or ()
        size = allocation.chamber_size or 0
        outside = sum(1 for d in winners if d.party is None) + sum(
            n for party, n in wins.items() if party not in eligible
        )
        if outside > size:
            raise ValueError(
                f"{self!r}: {outside} Wahlkreis seats are won outside the allocation, "
                f"more than the {size} seats of the chamber"
            )
        return allocation.with_values(seat_total=size - outside)
