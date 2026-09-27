"""Eligibility: which parties take part in the proportional allocation, and how many
seats it divides (e.g. Sec. 1 (1) and 35 (3), (4) LWG LSA)."""

from __future__ import annotations

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.threshold import Threshold
from wahlwerk.ids import LevelName, Slug
from wahlwerk.model import Seats
from wahlwerk.process.allocation.base import Allocation, AllocationStep, total_fact

__all__ = ["ApplyThreshold", "SetHouse", "SetSeatTotal"]


class ApplyThreshold(AllocationStep):
    """The parties that pass ``threshold`` on their valid votes in ``section``, summed
    at ``level``, become ``eligible``.

    The share is of all valid votes in the section, of every party. A threshold that
    counts seats already won (a Grundmandatsklausel) is given each party's Wahlkreis
    wins, so the step then also reads ``districts``.
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
            needed.add("districts")
        return frozenset(needed)

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"eligible"})

    def _apply(self, allocation: Allocation) -> Allocation:
        votes = allocation.votes_by_party(self.level, self.section)
        won = allocation.district_wins() if self.threshold.uses_won else None
        return allocation.with_values(eligible=self.threshold.select(votes, won))


class SetHouse(AllocationStep):
    """The house has ``seats`` seats to begin with: the legal minimum, e.g. 83
    (Sec. 1 (1) LWG LSA). A Mehrsitze rule may raise it later."""

    seats: Seats = Field(
        description="The seats of the house before any Mehrsitze, e.g. 83.",
    )

    @property
    def reads(self) -> frozenset[str]:
        return frozenset({"tally"})

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"house"})

    def _apply(self, allocation: Allocation) -> Allocation:
        return allocation.with_values(house=self.seats)


class SetSeatTotal(AllocationStep):
    """The seats the proportional allocation divides: the ``house`` less the Wahlkreis
    seats of winners who take no part in it, i.e. Einzelbewerber and parties that are
    not ``eligible``.

    Their seats are theirs regardless; the rest of the house is divided among the
    eligible parties, whose own Wahlkreis seats are deducted later.
    """

    @property
    def reads(self) -> frozenset[str]:
        return frozenset({"house", "districts", "eligible"})

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"seat_total"})

    def _apply(self, allocation: Allocation) -> Allocation:
        wins = allocation.district_wins()
        eligible = allocation.eligible or frozenset()
        districts = allocation.districts or ()
        house = allocation.house or 0
        outside = sum(1 for d in districts if d.party is None) + sum(
            n for party, n in wins.items() if party not in eligible
        )
        if outside > house:
            raise ValueError(
                f"{self!r}: {outside} Wahlkreis seats are won outside the allocation, "
                f"more than the {house} seats of the house"
            )
        return allocation.with_values(seat_total=house - outside)
