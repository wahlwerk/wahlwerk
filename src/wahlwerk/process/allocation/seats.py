"""Seats: each eligible party's entitlement, and how many of its seats come from its
list once its Wahlkreis seats are deducted (e.g. Sec. 35 (5) to (7) LWG LSA)."""

from __future__ import annotations

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.deduction import Deduction
from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk.ids import LevelName, Slug
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationStep,
    Column,
    counts_fact,
)

__all__ = ["ApportionSeats", "DeductUnitSeats"]


class ApportionSeats(AllocationStep):
    """Apportion ``seats_to_apportion`` by ``method`` among the columns of the table it
    takes, ``<section> by <level> × <by>`` (``zweitstimme by land × eligible party``), on
    their votes there: their ``entitlement``.

    A tie in the apportionment (equal remainders, equal quotients) is decided by the lot
    recorded with the vote for exactly that tie: this section, the table's unit (the Land
    when it has one row), these parties, as many seats. Any other tie stays in the
    entitlement, and :class:`DeductUnitSeats` stops on it.
    """

    method: SerializeAsAny[ApportionmentMethod] = Field(
        description="The method, e.g. ``MajorityFirst(method=HareNiemeyer())``.",
    )
    section: Slug = Field(
        description="The vote the seats follow, e.g. ``zweitstimme``.",
    )
    level: LevelName = Field(
        description="The level the votes are summed at, e.g. ``land``.",
    )
    by: Column = Field(
        default="eligible party",
        description=(
            "Whose votes: the parties past the threshold (``eligible party``), or, with no "
            "threshold, every ``party``."
        ),
    )

    @property
    def inputs(self) -> dict[str, str]:
        return {"votes": counts_fact(self.section, self.level, self.by), "seats": "seats_to_apportion"}

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"entitlement"})

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {"method": (("votes", "votes per party"), ("seats", "seats"))}

    def _apply(self, allocation: Allocation) -> Allocation:
        table = allocation.count(self.section, self.level, self.by)
        votes = table.per_column()
        seats = allocation.seats_to_apportion or 0
        entitlement = self.method.apportion(votes, seats)
        if entitlement.tie is not None:
            unit = table.rows[0][0] if len(table.rows) == 1 else None
            lot = allocation.lot_for(entitlement.tie, self.section, unit)
            if lot is not None:
                entitlement = entitlement.with_lot(lot.winners)
        return allocation.with_values(entitlement=entitlement)


class DeductUnitSeats(AllocationStep):
    """Deduct each eligible party's Wahlkreis seats from its entitlement: the rest are
    its ``list_seats``. Where a party won more Wahlkreise than it is entitled to, it
    keeps them, fills no list seat, and the excess is its ``overhang`` (Mehrsitze).

    Raises ``ValueError`` if the entitlement still holds a tie: the lot decides it first.
    """

    @property
    def inputs(self) -> dict[str, str]:
        return {"entitlement": "entitlement", "mandates": "unit_mandates"}

    deduction: Deduction = Field(
        default_factory=Deduction,
        description="How the Wahlkreis seats are taken off the entitlement: what is left, what is beyond.",
    )

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {"deduction": (("seats", "entitlement"), ("won", "mandates per party"))}

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"list_seats", "overhang"})

    def _apply(self, allocation: Allocation) -> Allocation:
        entitlement = allocation.entitlement
        if entitlement is None or not entitlement.is_decided:
            raise ValueError(f"{self!r}: the entitlement has a tie; the lot must be applied first")
        wins = allocation.unit_wins()
        entitled = dict(entitlement.seats)
        won = {party: wins.get(party, 0) for party in entitled}
        rest = self.deduction.left(entitled, won)
        over = self.deduction.excess(entitled, won)
        list_seats = tuple((party, rest[party]) for party in entitled)
        overhang = tuple((party, over[party]) for party in entitled if party in over)
        return allocation.with_values(list_seats=list_seats, overhang=overhang)
