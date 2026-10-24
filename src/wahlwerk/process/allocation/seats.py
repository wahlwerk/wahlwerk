"""Seats: each eligible party's entitlement, and how many of its seats come from its
list once its Wahlkreis seats are deducted (e.g. Sec. 35 (5) to (7) LWG LSA)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk.calc import compensation
from wahlwerk.ids import LevelName, Slug
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationStep,
    counts_fact,
    eligible_fact,
)

__all__ = ["ApportionSeats", "DeductUnitSeats"]


class ApportionSeats(AllocationStep):
    """Apportion ``seats_to_apportion`` among the eligible parties of ``section`` by ``method``, on their
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
    def inputs(self) -> dict[str, str]:
        return {
            "votes": counts_fact(self.section, self.level, "party"),
            "eligible": eligible_fact(self.section),
            "seats": "seats_to_apportion",
        }

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"entitlement"})

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {"method": (("votes", "votes of the eligible parties"), ("seats", "seats"))}

    def _apply(self, allocation: Allocation) -> Allocation:
        votes = allocation.count(self.section, self.level, "party").per_column()
        eligible = allocation.eligible(self.section)
        weights = {party: n for party, n in votes.items() if party in eligible}
        seats = allocation.seats_to_apportion or 0
        return allocation.with_values(entitlement=self.method.apportion(weights, seats))


class DeductUnitSeats(AllocationStep):
    """Deduct each eligible party's Wahlkreis seats from its entitlement: the rest are
    its ``list_seats``. Where a party won more Wahlkreise than it is entitled to, it
    keeps them, fills no list seat, and the excess is its ``overhang`` (Mehrsitze).

    Raises ``ValueError`` if the entitlement still holds a tie: the lot decides it first.
    """

    @property
    def inputs(self) -> dict[str, str]:
        return {"entitlement": "entitlement", "mandates": "unit_mandates"}

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (compensation.remaining, compensation.overhang)

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {"": (("seats", "entitlement"), ("won", "mandates per party"))}

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
        remaining, overhang_of = self.formulas
        rest = remaining(entitled, won) if entitled else {}
        over = overhang_of(entitled, won) if entitled else {}
        assert isinstance(rest, dict) and isinstance(over, dict)
        list_seats = tuple((party, rest[party]) for party in entitled)
        overhang = tuple((party, over[party]) for party in entitled if over[party] > 0)
        return allocation.with_values(list_seats=list_seats, overhang=overhang)
