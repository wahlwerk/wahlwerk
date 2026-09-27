"""Mehrsitze: raising the house when parties win more Wahlkreise than their entitlement
(e.g. Sec. 35 (8), (8a) LWG LSA)."""

from __future__ import annotations

from fractions import Fraction

from pydantic import Field, SerializeAsAny

from wahlwerk.ids import LevelName, Slug
from wahlwerk.model import Model, Share
from wahlwerk.process.allocation.base import Allocation, AllocationStep, total_fact

__all__ = ["FraktionSize", "RepeatForMehrsitze"]


class FraktionSize(Model):
    """The rule of Sec. 35 (8a) LWG LSA that :class:`RepeatForMehrsitze` uses: the seats needed for a Fraktion are the seats a
    fictitious party would at least get with ``share`` of all valid votes in ``section``,
    at the current stage of the allocation.

    The law does not say how the fictitious party enters the count (wahlrecht.de calls
    it unclear). Read here: it joins the eligible parties with ``share`` of all valid
    votes, and "at least" means the whole part of its Hare share of ``seat_total``, since
    a remainder seat is not certain.
    """

    share: Share = Field(
        description="The fictitious party's share of all valid votes, e.g. ``Fraction(5, 100)``.",
    )
    section: Slug = Field(
        description="The vote it is measured on, e.g. ``zweitstimme``.",
    )
    level: LevelName = Field(
        description="The level the votes are summed at, e.g. ``land``.",
    )

    @property
    def reads(self) -> frozenset[str]:
        """The facts it needs from the allocation."""
        return frozenset({total_fact(self.level), "eligible", "seat_total"})

    def seats(self, allocation: Allocation) -> int:
        """The seats needed for a Fraktion at this stage of ``allocation``."""
        votes = allocation.votes_by_party(self.level, self.section)
        eligible = allocation.eligible or frozenset()
        fictitious = self.share * sum(votes.values())
        counted = sum(n for party, n in votes.items() if party in eligible) + fictitious
        if not counted:
            return 0
        exact = Fraction(allocation.seat_total or 0) * fictitious / counted
        return exact.numerator // exact.denominator


class RepeatForMehrsitze(AllocationStep):
    """While a party holds Mehrsitze (``overhang``), raise the ``house`` and allocate
    again with ``protocol`` (the rules from the seat total to the list seats).

    As in Sec. 35 (8) LWG LSA: the first ``full_rounds`` times, the house grows by
    ``factor`` times the Mehrsitze and the allocation is repeated. After that, Mehrsitze
    that remain are kept unbalanced (the chamber then has that many seats more) unless
    they exceed half of ``fraktion``, in which case another round follows. Every seat
    won in a Wahlkreis is kept throughout.
    """

    protocol: tuple[SerializeAsAny[AllocationStep], ...] = Field(
        min_length=1,
        description="The steps repeated for the raised house, e.g. seat total, apportionment, deduction.",
    )
    factor: int = Field(
        default=2,
        ge=1,
        description="How many seats the house grows by per Mehrsitz, e.g. 2.",
    )
    full_rounds: int = Field(
        default=2,
        ge=0,
        description="How many rounds are repeated whatever the number of Mehrsitze.",
    )
    fraktion: FraktionSize | None = Field(
        default=None,
        description=(
            "The Fraktion size limiting further rounds; ``None`` for no further rounds "
            "after the full ones."
        ),
    )

    @property
    def reads(self) -> frozenset[str]:
        inner = frozenset().union(*(step.reads for step in self.protocol))
        extra = self.fraktion.reads if self.fraktion else frozenset()
        return frozenset({"house", "overhang"}) | inner | extra

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"house"}).union(*(step.writes for step in self.protocol))

    def _apply(self, allocation: Allocation) -> Allocation:
        rounds = 0
        while mehrsitze := sum(n for _, n in allocation.overhang or ()):
            if rounds >= self.full_rounds:
                limit = self.fraktion.seats(allocation) if self.fraktion else None
                if limit is None or 2 * mehrsitze <= limit:
                    break
            house = (allocation.house or 0) + self.factor * mehrsitze
            allocation = allocation.with_values(house=house)
            for step in self.protocol:
                allocation = step.apply(allocation)
            rounds += 1
        return allocation
