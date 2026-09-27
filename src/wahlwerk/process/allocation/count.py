"""Counting: the tally summed to the levels the law counts at (e.g. Sec. 31, 32 and
35 (2) LWG LSA: per Wahlkreis, then per Land)."""

from __future__ import annotations

from pydantic import Field

from wahlwerk.ids import LevelName
from wahlwerk.process.allocation.base import Allocation, AllocationStep, total_fact

__all__ = ["SumVotes"]


class SumVotes(AllocationStep):
    """Sum the whole tally to ``level`` of its main hierarchy, e.g. ``wahlkreis``.

    Every row is summed, votes, invalid votes and people alike, keeping sections and
    channels apart; later steps pick what they need. Summing a level again replaces the
    earlier total.
    """

    level: LevelName = Field(
        description="The level to sum to, as listed in the tally's levels, e.g. ``wahlkreis``.",
    )

    @property
    def reads(self) -> frozenset[str]:
        return frozenset({"tally"})

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({total_fact(self.level)})

    def _apply(self, allocation: Allocation) -> Allocation:
        summed = allocation.tally.sum_to(self.level)
        others = tuple((level, t) for level, t in allocation.totals if level != self.level)
        return allocation.with_values(totals=(*others, (self.level, summed)))
