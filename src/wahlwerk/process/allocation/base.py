"""The working record of an allocation, and the steps and protocols that build it.

An allocation turns the tally of a popular vote into seats under an electoral law. The
law is an :data:`AllocationProtocol`, an ordered tuple of :class:`AllocationStep`; each
step reads facts from the :class:`Allocation` and adds or replaces others, e.g. the
votes summed per Wahlkreis, then the Wahlkreis winners. The allocation exists only
while the result is derived, so it lives here and not in ``state``.

Every step declares the facts it reads and writes. :func:`check_protocol` walks a
protocol and refuses one that reads a fact before any step writes it, so a law written
in the wrong order fails when it is checked, not halfway through a run; each step checks
its own facts again when applied.

Facts are named by strings: ``tally`` (the input), ``total:<level>`` (the tally summed
to a level, see :class:`~wahlwerk.process.allocation.count.SumVotes`), and one per
optional field of :class:`Allocation`, named like it: ``districts``, ``eligible``,
``house``, ``seat_total``, ``entitlement``, ``list_seats``, ``overhang``, ``chamber``.
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import Any

from pydantic import Field, model_validator

from wahlwerk.apportionment.result import Apportionment
from wahlwerk.apportionment.tie import Tie
from wahlwerk.ids import CandidateId, LevelName, PartyId, UnitId
from wahlwerk.model import Count, Model, Seats
from wahlwerk.state.chamber import Chamber
from wahlwerk.vote.popular.tally import Tally, TallyKind

__all__ = [
    "INPUT_FACTS",
    "OPTIONAL_FACTS",
    "Allocation",
    "AllocationProtocol",
    "AllocationStep",
    "DistrictResult",
    "check_protocol",
    "total_fact",
]

logger = logging.getLogger(__name__)

INPUT_FACTS = frozenset({"tally"})
"""The facts every allocation starts with."""

OPTIONAL_FACTS = (
    "districts",
    "eligible",
    "house",
    "seat_total",
    "entitlement",
    "list_seats",
    "overhang",
    "chamber",
)
"""The facts held by an optional field of :class:`Allocation` of the same name."""


def total_fact(level: str) -> str:
    """The name of the fact holding the tally summed to ``level``: ``total:<level>``."""
    return f"total:{level}"


class DistrictResult(Model):
    """Who won one single-seat unit (a Wahlkreis), or who tied for it.

    The winner is a nominee: a candidate where the tally names one, otherwise a party's
    nomination. ``party`` is the party that nominated the winner, ``None`` for an
    Einzelbewerber. When the most votes are shared, ``tie`` names the nominees and no
    winner is set; the lot is drawn by an official and applied later.
    """

    unit: UnitId = Field(
        description="The unit, e.g. ``de.st.wk.001``.",
    )
    nominee: str | None = Field(
        default=None,
        description="The winning nominee: its candidate id, or its party id; ``None`` on a tie.",
    )
    party: PartyId | None = Field(
        default=None,
        description="The party that nominated the winner; ``None`` for an Einzelbewerber or on a tie.",
    )
    candidate: CandidateId | None = Field(
        default=None,
        description="The winning candidate, where the tally names one.",
    )
    votes: Count = Field(
        description="The winner's votes, or each tied nominee's.",
    )
    tie: Tie | None = Field(
        default=None,
        description="The nominees with equally many votes, for one seat; ``None`` if decided.",
    )

    @model_validator(mode="after")
    def _check_winner_or_tie(self) -> DistrictResult:
        if (self.nominee is None) == (self.tie is None):
            raise ValueError(
                f"district {self.unit!r} needs a winner or a tie, not both or neither "
                f"(nominee={self.nominee!r}, tie={self.tie!r})"
            )
        if self.tie is not None and self.tie.seats != 1:
            raise ValueError(f"district {self.unit!r} has one seat, but the tie is over {self.tie.seats}")
        return self

    @property
    def is_decided(self) -> bool:
        """Whether a winner is set, i.e. there is no tie."""
        return self.tie is None


class Allocation(Model):
    """What the law has established so far about one popular vote.

    Starts from the ``tally`` alone; each step adds facts. A fact not yet established is
    absent (``None``, or no entry in ``totals``), never a placeholder.
    """

    tally: Tally = Field(
        description="The tally of the popular vote, as recorded.",
    )
    totals: tuple[tuple[LevelName, Tally], ...] = Field(
        default_factory=tuple,
        description="The tally summed to each level a step asked for, in the order summed.",
    )
    districts: tuple[DistrictResult, ...] | None = Field(
        default=None,
        description="The result of each single-seat unit; ``None`` until decided.",
    )
    eligible: frozenset[PartyId] | None = Field(
        default=None,
        description="The parties taking part in the proportional allocation, past the threshold.",
    )
    house: Seats | None = Field(
        default=None,
        description=(
            "The number of seats the house has at this stage: the legal minimum, then "
            "as raised for Mehrsitze."
        ),
    )
    seat_total: Seats | None = Field(
        default=None,
        description="The seats apportioned among the eligible parties' lists and Wahlkreise.",
    )
    entitlement: Apportionment | None = Field(
        default=None,
        description="The seats each eligible party is entitled to in total.",
    )
    list_seats: tuple[tuple[PartyId, Seats], ...] | None = Field(
        default=None,
        description="The seats each eligible party fills from its list, after its Wahlkreis seats.",
    )
    overhang: tuple[tuple[PartyId, Seats], ...] | None = Field(
        default=None,
        description=(
            "The Wahlkreis seats each party won beyond its entitlement (Überhang, "
            "Mehrsitze), for the parties that have any."
        ),
    )
    chamber: Chamber | None = Field(
        default=None,
        description="The chamber the allocation forms, its last fact.",
    )

    @model_validator(mode="after")
    def _check_totals(self) -> Allocation:
        levels = [level for level, _ in self.totals]
        if len(set(levels)) != len(levels):
            raise ValueError(f"allocation sums a level more than once: {levels}")
        return self

    @property
    def facts(self) -> frozenset[str]:
        """The names of the facts established so far."""
        facts = set(INPUT_FACTS)
        facts.update(total_fact(level) for level, _ in self.totals)
        facts.update(name for name in OPTIONAL_FACTS if getattr(self, name) is not None)
        return frozenset(facts)

    def district_wins(self) -> dict[str, int]:
        """The Wahlkreise each party won, from ``districts``. Raises ``ValueError`` if
        they are not decided yet, or a tie in one is still to be decided by lot."""
        if self.districts is None:
            raise ValueError("the Wahlkreise are not decided yet")
        tied = [d.unit for d in self.districts if not d.is_decided]
        if tied:
            raise ValueError(f"Wahlkreise {tied} are tied; the lot must be applied first")
        wins: dict[str, int] = {}
        for district in self.districts:
            if district.party is not None:
                wins[district.party] = wins.get(district.party, 0) + 1
        return wins

    def total(self, level: str) -> Tally:
        """The tally summed to ``level``; raises ``KeyError`` naming the level if it was
        not summed."""
        for name, tally in self.totals:
            if name == level:
                return tally
        raise KeyError(f"allocation has no total at level {level!r}; summed: {[n for n, _ in self.totals]}")

    def votes_by_party(self, level: str, section: str) -> dict[str, int]:
        """The valid votes in ``section`` per party, from the total at ``level``, summed
        over units and channels; votes for no party (Einzelbewerber) are left out."""
        votes = self.total(level).filter(kind=TallyKind.VOTES, section=section)
        return {party: n for party, n in votes.sum_by("party").items() if party is not None}

    def with_values(self, **changes: Any) -> Allocation:
        """This allocation with ``changes`` in place of its fields, validated."""
        return type(self).model_validate({**dict(self), **changes})


class AllocationStep(Model):
    """One rule of an electoral law: an allocation in, an allocation out.

    Subclasses implement :meth:`_apply` and declare :attr:`reads` and :attr:`writes`.
    Callable, so ``step(allocation)`` is ``step.apply(allocation)``.
    """

    @property
    @abstractmethod
    def reads(self) -> frozenset[str]:
        """The facts this step needs."""

    @property
    @abstractmethod
    def writes(self) -> frozenset[str]:
        """The facts this step establishes or replaces."""

    @abstractmethod
    def _apply(self, allocation: Allocation) -> Allocation:
        """The allocation with this step's facts, given that its reads are established."""

    def apply(self, allocation: Allocation) -> Allocation:
        """Apply this step. Raises ``ValueError`` naming the step if a fact it reads is
        missing, or if it did not establish every fact it writes."""
        missing = self.reads - allocation.facts
        if missing:
            raise ValueError(f"{self!r} reads {sorted(missing)}, which are not established")
        logger.debug("applying %r", self)
        result = self._apply(allocation)
        unwritten = self.writes - result.facts
        if unwritten:
            raise ValueError(f"{self!r} did not establish {sorted(unwritten)}")
        return result

    def __call__(self, allocation: Allocation) -> Allocation:
        return self.apply(allocation)


AllocationProtocol = tuple[AllocationStep, ...]
"""An electoral law as an ordered protocol of allocation steps, applied first to last."""


def check_protocol(
    protocol: AllocationProtocol, established: frozenset[str] = INPUT_FACTS
) -> frozenset[str]:
    """Check that each step of ``protocol`` reads only facts established before it,
    starting from ``established``; return the facts established at the end.

    Raises ``ValueError`` naming the first step that reads a missing fact, and its
    position.
    """
    facts = set(established)
    for position, step in enumerate(protocol, start=1):
        missing = step.reads - facts
        if missing:
            raise ValueError(
                f"step {position} {step!r} reads {sorted(missing)}, "
                f"which no earlier step writes; established: {sorted(facts)}"
            )
        facts |= step.writes
    return frozenset(facts)
