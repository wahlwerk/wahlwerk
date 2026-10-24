"""Eligibility: which parties take part in the proportional allocation, and how many
seats it divides (e.g. Sec. 1 (1) and 35 (3), (4) LWG LSA)."""

from __future__ import annotations

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.deduction import Deduction
from wahlwerk.apportionment.threshold import Threshold
from wahlwerk.ids import LevelName, Slug
from wahlwerk.model import Seats
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationStep,
    GroupBy,
    counts_fact,
    eligible_fact,
)

__all__ = ["ApplyThresholdTo", "SetChamberSize", "SetSeatsToApportion"]


class ApplyThresholdTo(AllocationStep):
    """Apply ``threshold`` to the parties (or, ``to="option"``, the options) of a vote:
    those that pass it on their valid votes in ``section``, summed at ``level``, become
    the fact ``eligible parties of <section>`` (``eligible parties of zweitstimme``), or
    ``eligible options of <section>``. A law with thresholds on two votes keeps two such
    facts.

    It takes the table ``<section> by <level> × <to>``. The share is of all valid votes
    counted there. A threshold that counts seats already won (a Grundmandatsklausel) is
    given each party's Wahlkreis wins, so the step then also reads ``unit_mandates``.
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
    to: GroupBy = Field(
        default="party",
        description="What the threshold is applied to: each ``party``, or each ``option``.",
    )

    @property
    def inputs(self) -> dict[str, str]:
        given = {"votes": counts_fact(self.section, self.level, self.to)}
        if self.threshold.uses_won:
            given["mandates"] = "unit_mandates"
        return given

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({eligible_fact(self.section, self.to)})

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        given: tuple[tuple[str, str], ...] = (("votes", f"votes per {self.to}, summed over the units"),)
        if self.threshold.uses_won:
            given += (("won", "mandates per party"),)
        return {"threshold": given}

    def _apply(self, allocation: Allocation) -> Allocation:
        votes = allocation.count(self.section, self.level, self.to).per_column()
        won = allocation.unit_wins() if self.threshold.uses_won else None
        fact = eligible_fact(self.section, self.to)
        others = tuple((f, p) for f, p in allocation.passed if f != fact)
        return allocation.with_values(passed=(*others, (fact, self.threshold.select(votes, won))))


class SetChamberSize(AllocationStep):
    """The chamber has ``seats`` seats to begin with, e.g. 83 (Sec. 1 (1) LWG LSA); a
    Mehrsitze or Ausgleich rule may raise the size later.

    Where the law says "at least" ("mindestens 83"), the same number is the chamber's
    minimum (``is_minimum``), which stays when the size is raised: one number in the law,
    written once here. A law whose minimum differs from its size sets ``is_minimum`` false
    and gives the minimum to :class:`~wahlwerk.process.allocation.chamber.FillVacantSeatsFromLists`.
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
        return frozenset()

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"chamber_size", "minimum_mandates"} if self.is_minimum else {"chamber_size"})

    def _apply(self, allocation: Allocation) -> Allocation:
        if self.is_minimum:
            return allocation.with_values(chamber_size=self.seats, minimum_mandates=self.seats)
        return allocation.with_values(chamber_size=self.seats)


class SetSeatsToApportion(AllocationStep):
    """The seats the proportional allocation divides: the ``chamber_size`` less the Wahlkreis
    seats whose mandates take no part in it, read off ``unit_mandates``: those of no party
    (Einzelbewerber) and those of parties that are not eligible parties of ``section``.

    Their seats are theirs regardless; the rest of the chamber size is divided among the
    eligible parties, whose own Wahlkreis seats are deducted later.
    """

    section: Slug = Field(
        description="The vote whose eligible parties the seats are divided among, e.g. ``zweitstimme``.",
    )
    deduction: Deduction = Field(
        default_factory=Deduction,
        description="How the seats won outside are taken off the chamber size.",
    )

    @property
    def inputs(self) -> dict[str, str]:
        return {
            "size": "chamber_size",
            "mandates": "unit_mandates",
            "eligible": eligible_fact(self.section),
        }

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {"deduction": (("seats", "size"), ("won", "mandates of no party or of a party not eligible"))}

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"seats_to_apportion"})

    def _apply(self, allocation: Allocation) -> Allocation:
        wins = allocation.unit_wins()
        eligible = allocation.eligible(self.section)
        size = allocation.chamber_size or 0
        mandates = allocation.unit_mandates or ()
        outside = sum(1 for d in mandates if d.party is None) + sum(
            n for party, n in wins.items() if party not in eligible
        )
        if outside > size:
            raise ValueError(
                f"{self!r}: {outside} Wahlkreis seats are won outside the allocation, "
                f"more than the {size} seats of the chamber"
            )
        left = self.deduction.left({"chamber": size}, {"chamber": outside})
        return allocation.with_values(seats_to_apportion=left["chamber"])
