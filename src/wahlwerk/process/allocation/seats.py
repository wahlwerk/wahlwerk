"""Seats: each eligible party's entitlement, and how many of its seats come from its
list once its Wahlkreis seats are deducted (e.g. Sec. 35 (5) to (7) LWG LSA)."""

from __future__ import annotations

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk.ids import LevelName, Slug
from wahlwerk.process.allocation.base import Allocation, AllocationStep, total_fact

__all__ = ["ApportionSeats", "DeductDistrictSeats"]


class ApportionSeats(AllocationStep):
    """Apportion ``seat_total`` among the ``eligible`` parties by ``method``, on their
    valid votes in ``section`` summed at ``level``: their ``entitlement``.

    A tie in the apportionment stays in the entitlement; the lot is applied before the
    seats are used.
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

    @property
    def reads(self) -> frozenset[str]:
        return frozenset({total_fact(self.level), "eligible", "seat_total"})

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"entitlement"})

    def _apply(self, allocation: Allocation) -> Allocation:
        votes = allocation.votes_by_party(self.level, self.section)
        eligible = allocation.eligible or frozenset()
        weights = {party: n for party, n in votes.items() if party in eligible}
        seats = allocation.seat_total or 0
        return allocation.with_values(entitlement=self.method.apportion(weights, seats))


class DeductDistrictSeats(AllocationStep):
    """Deduct each eligible party's Wahlkreis seats from its entitlement: the rest are
    its ``list_seats``. Where a party won more Wahlkreise than it is entitled to, it
    keeps them, fills no list seat, and the excess is its ``overhang`` (Mehrsitze).

    Raises ``ValueError`` if the entitlement still holds a tie: the lot decides it first.
    """

    @property
    def reads(self) -> frozenset[str]:
        return frozenset({"entitlement", "districts"})

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"list_seats", "overhang"})

    def _apply(self, allocation: Allocation) -> Allocation:
        entitlement = allocation.entitlement
        if entitlement is None or not entitlement.is_decided:
            raise ValueError(f"{self!r}: the entitlement has a tie; the lot must be applied first")
        wins = allocation.district_wins()
        list_seats = tuple(
            (party, max(entitled - wins.get(party, 0), 0)) for party, entitled in entitlement.seats
        )
        overhang = tuple(
            (party, wins.get(party, 0) - entitled)
            for party, entitled in entitlement.seats
            if wins.get(party, 0) > entitled
        )
        return allocation.with_values(list_seats=list_seats, overhang=overhang)
