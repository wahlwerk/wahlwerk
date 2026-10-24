"""Counting: the valid votes of one section grouped by the units of a level and by
option, and summed (e.g. Sec. 31, 32 and 35 (2) LWG LSA: the Erststimmen per Wahlkreis,
the Zweitstimmen in the Land)."""

from __future__ import annotations

from pydantic import Field

from wahlwerk.ids import LevelName, Slug
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationStep,
    Counts,
    counts_fact,
)
from wahlwerk.vote.popular.tally import TallyKind

__all__ = ["SumGroupBy"]


class SumGroupBy(AllocationStep):
    """Sum the valid votes of ``section``, grouped by the units of ``level`` and by
    option: the table ``<level>:option:<section>`` (``wahlkreis:option:erststimme``),
    a row per unit, a counter per option, channels (Urne and Brief) summed.

    Only valid votes are counted, so invalid votes and people are not in it. Each
    option's party is taken along; an option recorded with two parties is refused.
    Making a table again replaces it.
    """

    section: Slug = Field(description="The vote to count, e.g. ``erststimme``.")
    level: LevelName = Field(
        description="The level to group by, as listed in the tally's levels, e.g. ``wahlkreis``.",
    )

    @property
    def inputs(self) -> dict[str, str]:
        return {"tally": "tally"}

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({counts_fact(self.level, self.section)})

    def _apply(self, allocation: Allocation) -> Allocation:
        # Sum the whole tally to the level first: a tally keeps its sums, so every law
        # replayed on one vote sums it once; then keep this section's votes.
        summed = allocation.tally.sum_to(self.level).filter(kind=TallyKind.VOTES, section=self.section)
        rows: dict[str, dict[str, int]] = {}
        parties: dict[str, str | None] = {}
        for row in summed.rows:
            option = row.option
            assert option is not None  # a VOTES row always names its option
            if parties.setdefault(option, row.party) != row.party:
                raise ValueError(
                    f"{self!r}: option {option!r} stands for {parties[option]!r} and {row.party!r}"
                )
            votes = rows.setdefault(row.unit, {})
            votes[option] = votes.get(option, 0) + row.count
        table = Counts(
            level=self.level,
            section=self.section,
            rows=tuple((unit, tuple(votes.items())) for unit, votes in rows.items()),
            parties=tuple(parties.items()),
        )
        others = tuple(t for t in allocation.counts if t.fact != table.fact)
        return allocation.with_values(counts=(*others, table))
