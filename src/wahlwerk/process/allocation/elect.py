"""Units that elect one member each: a winner per unit of a level.

Two parts, kept apart so each is visible. The step turns the tally into one small
contest per unit: the options standing there and their votes, a row of the table of counts. A method then chooses
the winner from that list alone, knowing nothing of units, sections or law; usually
:class:`~wahlwerk.apportionment.plurality.Plurality`, the most votes win. In Germany
the units are Wahlkreise and the vote is the Erststimme (Sec. 33 LWG LSA: the most
Erststimmen; lot on a tie); elsewhere constituencies or ridings: here, units of a level.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.method import ApportionmentMethod
from wahlwerk.apportionment.tie import Tie
from wahlwerk.ids import LevelName, Slug
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationStep,
    Counts,
    UnitResult,
    counts_fact,
)

__all__ = ["SingleMandatePerUnit"]


class SingleMandatePerUnit(AllocationStep):
    """One mandate per unit: elect one option in each unit of ``level`` by ``method``, from
    the valid votes in ``section`` summed over channels (Urne and Brief).

    Its argument ``votes`` is the table ``<section> by <level> × option``: each row one unit's
    contest, its options and their votes, an option being a candidate, or a party's
    nominee where the tally names no candidate. ``method`` chooses one winner from a row
    alone. Where it cannot (equal votes at the top, or no votes at all), the unit's
    result is a :class:`~wahlwerk.apportionment.tie.Tie`, since the law decides it by
    lot; nothing is guessed. A lot recorded with the vote for exactly that tie (this
    section, this unit, these options) decides it, and the result keeps the lot; any other
    tie stays. The winner's party is the option's, from the table.
    """

    SEATS: ClassVar[int] = 1
    """Each unit elects one member: the seats handed to ``method`` per contest."""

    method: SerializeAsAny[ApportionmentMethod] = Field(
        description=(
            "How one winner is chosen from a unit's options and their votes, e.g. "
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
    def inputs(self) -> dict[str, str]:
        return {"votes": counts_fact(self.section, self.level, "option")}

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"unit_mandates"})

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {"method": (("votes", "one row of votes"), ("seats", str(self.SEATS)))}

    def _apply(self, allocation: Allocation) -> Allocation:
        table = allocation.count(self.section, self.level, "option")
        if not table.rows:
            raise ValueError(f"{type(self).__name__}: no {table.fact!r} votes to elect from")
        return allocation.with_values(
            unit_mandates=tuple(
                self._elect(unit, votes, table, allocation) for unit, votes in table.per_unit().items()
            )
        )

    def _elect(self, unit: str, votes: dict[str, int], table: Counts, allocation: Allocation) -> UnitResult:
        """The winner of one unit's contest, chosen by ``method``."""
        most = max(votes.values())
        if most:
            result = self.method.apportion(votes, self.SEATS)
            tie = result.tie
            winners = [option for option, seats in result.seats if seats]
        else:  # no votes at all: every option is equally placed
            tie = Tie(candidates=frozenset(votes), seats=1)
            winners = []
        if tie is not None:
            lot = allocation.lot_for(tie, self.section, unit)
            if lot is None:
                return UnitResult.model_validate({"unit": unit, "votes": most, "tie": tie})
            (drawn,) = lot.winners
            return UnitResult.model_validate(
                {"unit": unit, "option": drawn, "party": table.party_of(drawn), "votes": most, "lot": lot}
            )
        (option,) = winners
        return UnitResult.model_validate(
            {"unit": unit, "option": option, "party": table.party_of(option), "votes": votes[option]}
        )
