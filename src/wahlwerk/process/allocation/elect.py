"""Units that elect one member each: a winner per unit of a level.

Two parts, kept apart so each is visible. The step turns the tally into one small
contest per unit: the nominees standing there and their votes. A method then chooses
the winner from that list alone, knowing nothing of units, sections or law; usually
:class:`~wahlwerk.apportionment.plurality.Plurality`, the most votes win. In Germany
the units are Wahlkreise and the vote is the Erststimme (Sec. 33 LWG LSA: the most
Erststimmen; lot on a tie); elsewhere constituencies or ridings: here, units of a level.
"""

from __future__ import annotations

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk.apportionment.tie import Tie
from wahlwerk.ids import LevelName, Slug
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationStep,
    UnitResult,
    total_fact,
)
from wahlwerk.vote.popular.tally import TallyKind

__all__ = ["ElectPerUnit", "contests"]

Nominee = tuple[str | None, str | None]
"""A nominee as a tally names it: (party, candidate), either may be missing."""


class ElectPerUnit(AllocationStep):
    """Elect one nominee in each unit of ``level`` by ``method``, from the valid votes
    in ``section`` summed over channels (Urne and Brief).

    Each unit is one contest (:func:`contests`): its nominees and their votes, a
    nominee being the candidate a row names, or else the party it names. ``method``
    chooses one winner from that list. Where it cannot (equal votes at the top, or no
    votes at all), the unit's result is a :class:`~wahlwerk.apportionment.tie.Tie`, since
    the law decides it by lot; nothing is guessed.
    """

    method: SerializeAsAny[ApportionmentMethod] = Field(
        description=(
            "How one winner is chosen from a unit's nominees and their votes, e.g. "
            "``Plurality()``: the most votes win."
        ),
    )
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
        return frozenset({"unit_winners"})

    def _apply(self, allocation: Allocation) -> Allocation:
        per_unit = contests(allocation, self.section, self.level)
        if not per_unit:
            raise ValueError(
                f"{type(self).__name__}: no {self.section!r} votes at level {self.level!r} to elect from"
            )
        return allocation.with_values(
            unit_winners=tuple(self._elect(unit, nominees) for unit, nominees in per_unit.items())
        )

    def _elect(self, unit: str, nominees: dict[Nominee, int]) -> UnitResult:
        """The winner of one unit's contest, chosen by ``method``."""
        keys = {(candidate or party): (party, candidate) for party, candidate in nominees}
        votes = {key: nominees[keys[key]] for key in keys if key}
        most = max(votes.values())
        if most:
            result = self.method.apportion(votes, 1)
            tie = result.tie
            winners = [key for key, seats in result.seats if seats]
        else:  # no votes at all: every nominee is equally placed
            tie = Tie(candidates=frozenset(votes), seats=1)
            winners = []
        if tie is not None:
            return UnitResult.model_validate({"unit": unit, "votes": most, "tie": tie})
        (key,) = winners
        party, candidate = keys[key]
        return UnitResult.model_validate(
            {"unit": unit, "nominee": key, "party": party, "candidate": candidate, "votes": votes[key]}
        )


def contests(allocation: Allocation, section: str, level: str) -> dict[str, dict[Nominee, int]]:
    """The tally as one contest per unit of ``level``: each nominee in ``section`` and
    the valid votes for it, summed over channels."""
    votes = allocation.total(level).filter(kind=TallyKind.VOTES, section=section)
    per_unit: dict[str, dict[Nominee, int]] = {}
    for (unit, party, candidate), count in votes.sum_by("unit", "party", "candidate").items():
        per_unit.setdefault(unit, {})[(party, candidate)] = count
    return per_unit
