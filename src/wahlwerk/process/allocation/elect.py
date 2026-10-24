"""Units that elect one member each: a winner per unit of a level.

Two parts, kept apart so each is visible. The step turns the tally into one small
contest per unit: the options standing there and their votes. A method then chooses
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
    UnitResult,
    total_fact,
)
from wahlwerk.vote.popular.tally import TallyKind

__all__ = ["SingleMandatePerUnit", "contests", "parties_of"]

class SingleMandatePerUnit(AllocationStep):
    """One mandate per unit: elect one option in each unit of ``level`` by ``method``, from
    the valid votes in ``section`` summed over channels (Urne and Brief).

    Each unit is one contest (:func:`contests`): its options and their votes, an option
    being a candidate, or a party's nominee where the tally names no candidate.
    ``method`` chooses one winner from that list. Where it cannot (equal votes at the
    top, or no votes at all), the unit's result is a
    :class:`~wahlwerk.apportionment.tie.Tie`, since the law decides it by lot; nothing is
    guessed. The winner's party comes from the tally (:func:`parties_of`).
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
    def reads(self) -> frozenset[str]:
        return frozenset({total_fact(self.level)})

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"unit_mandates"})

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {"method": (("votes", f"{self.section} per option"), ("seats", str(self.SEATS)))}

    def _apply(self, allocation: Allocation) -> Allocation:
        per_unit = contests(allocation, self.section, self.level)
        if not per_unit:
            raise ValueError(
                f"{type(self).__name__}: no {self.section!r} votes at level {self.level!r} to elect from"
            )
        parties = parties_of(allocation, self.section, self.level)
        return allocation.with_values(
            unit_mandates=tuple(self._elect(unit, votes, parties) for unit, votes in per_unit.items())
        )

    def _elect(self, unit: str, votes: dict[str, int], parties: dict[str, str | None]) -> UnitResult:
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
            return UnitResult.model_validate({"unit": unit, "votes": most, "tie": tie})
        (option,) = winners
        return UnitResult.model_validate(
            {"unit": unit, "option": option, "party": parties.get(option), "votes": votes[option]}
        )


def contests(allocation: Allocation, section: str, level: str) -> dict[str, dict[str, int]]:
    """The tally as one contest per unit of ``level``: each option in ``section`` and
    the valid votes for it, summed over channels. A plain list of options and votes,
    which is all a method needs."""
    votes = allocation.total(level).filter(kind=TallyKind.VOTES, section=section)
    per_unit: dict[str, dict[str, int]] = {}
    for (unit, option), count in votes.sum_by("unit", "option").items():
        per_unit.setdefault(unit, {})[option] = count
    return per_unit


def parties_of(allocation: Allocation, section: str, level: str) -> dict[str, str | None]:
    """Each option's party in ``section`` at ``level``, as the tally records it; ``None``
    for an Einzelbewerber. Raises ``ValueError`` for an option recorded with two
    parties."""
    votes = allocation.total(level).filter(kind=TallyKind.VOTES, section=section)
    parties: dict[str, str | None] = {}
    for option, party in votes.sum_by("option", "party"):
        if parties.setdefault(option, party) != party:
            raise ValueError(f"option {option!r} stands for {parties[option]!r} and {party!r}")
    return parties
