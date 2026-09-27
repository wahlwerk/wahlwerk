"""Single-seat units: who wins each Wahlkreis (e.g. Sec. 33 LWG LSA: the most
Erststimmen; lot on a tie)."""

from __future__ import annotations

from pydantic import Field

from wahlwerk.apportionment.tie import Tie
from wahlwerk.ids import LevelName, Slug
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationStep,
    DistrictResult,
    total_fact,
)
from wahlwerk.vote.popular.tally import TallyKind

__all__ = ["ElectDistricts"]


class ElectDistricts(AllocationStep):
    """Elect one nominee per unit of ``level``: the one with the most valid votes in
    ``section``, summed over channels (Urne and Brief).

    A nominee is the candidate a row names, or else the party it names. Where the most
    votes are shared, the unit's result is a :class:`~wahlwerk.apportionment.tie.Tie`,
    since the law decides it by lot; nothing is guessed.
    """

    section: Slug = Field(
        description="The vote that elects in the units, e.g. ``erststimme``.",
    )
    level: LevelName = Field(
        description="The level of the single-seat units, e.g. ``wahlkreis``.",
    )

    @property
    def reads(self) -> frozenset[str]:
        return frozenset({total_fact(self.level)})

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"districts"})

    def _apply(self, allocation: Allocation) -> Allocation:
        votes = allocation.total(self.level).filter(kind=TallyKind.VOTES, section=self.section)
        per_unit: dict[str, dict[tuple[str | None, str | None], int]] = {}
        for (unit, party, candidate), count in votes.sum_by("unit", "party", "candidate").items():
            per_unit.setdefault(unit, {})[(party, candidate)] = count
        if not per_unit:
            raise ValueError(
                f"{self!r}: no {self.section!r} votes at level {self.level!r} to elect from"
            )
        return allocation.with_values(
            districts=tuple(_elect(unit, nominees) for unit, nominees in per_unit.items())
        )


def _elect(unit: str, nominees: dict[tuple[str | None, str | None], int]) -> DistrictResult:
    most = max(nominees.values())
    top = [(party, candidate) for (party, candidate), count in nominees.items() if count == most]
    if len(top) > 1:
        tied = frozenset(key for party, candidate in top if (key := candidate or party))
        return DistrictResult.model_validate(
            {"unit": unit, "votes": most, "tie": Tie(candidates=tied, seats=1)}
        )
    party, candidate = top[0]
    return DistrictResult.model_validate(
        {
            "unit": unit,
            "nominee": candidate or party,
            "party": party,
            "candidate": candidate,
            "votes": most,
        }
    )
