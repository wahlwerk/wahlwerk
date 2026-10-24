"""Overhang: raising the chamber size when parties win more units than their
entitlement, and allocating again. Two ways a law does it: by a multiple of the overhang
for a few rounds (:class:`RaiseByOverhang`; the Mehrsitze of Sec. 35 (8), (8a) LWG LSA),
or a seat at a time until it is balanced (:class:`RaiseUntilBalanced`; the Überhang- and
Ausgleichsmandate of Sec. 58 (6) LKWG M-V). :class:`CaucusSize` is the yardstick the
first uses to decide whether another round is due."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import Field, SerializeAsAny

from wahlwerk.calc import quota
from wahlwerk.ids import LevelName, Slug
from wahlwerk.model import Model, Share
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationProtocol,
    AllocationStep,
    outside_reads,
    total_fact,
    written_by,
)

__all__ = ["CaucusSize", "RaiseByOverhang", "RaiseUntilBalanced"]


class CaucusSize(Model):
    """The size of a caucus (a Fraktion), as Sec. 35 (8a) LWG LSA measures it for
    :class:`RaiseByOverhang`: the seats a fictitious party would at least get with
    ``share`` of all valid votes in ``section``, at the current stage of the allocation.

    The law does not say how the fictitious party enters the count (wahlrecht.de calls
    it unclear). Read here: it joins the eligible parties with ``share`` of all valid
    votes, and "at least" means the whole part of its Hare share of ``seat_total``, since
    a remainder seat is not certain.
    """

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (quota.hare, quota.whole_seats)

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
        """The seats needed for a caucus at this stage of ``allocation``: the Hare quota
        of the votes counted (the eligible parties and the fictitious one) for the seat
        total, and the whole seats the fictitious party's votes make of it."""
        votes = allocation.votes_by_party(self.level, self.section)
        eligible = allocation.eligible or frozenset()
        fictitious = self.share * sum(votes.values())
        counted = sum(n for party, n in votes.items() if party in eligible) + fictitious
        if not counted or not allocation.seat_total:
            return 0
        hare, whole_seats = self.formulas
        seats: int = whole_seats(fictitious, hare(counted, allocation.seat_total))
        return seats


class RaiseByOverhang(AllocationStep):
    """Allocate the seats of the chamber size with ``protocol`` (the rules from the seat
    total to the list seats, usually one :class:`~wahlwerk.process.allocation.sequence.StepSequence`);
    then, while a party holds overhang (Mehrsitze in the LWG LSA), raise the ``chamber_size`` and
    allocate again. The loop holds its allocation, so a law writes it once.

    As in Sec. 35 (8) LWG LSA: the first ``full_rounds`` times, the chamber size grows by
    ``factor`` times the overhang and the allocation is repeated. After that, overhang
    that remains is kept unbalanced (the chamber then has that many seats more) unless
    it exceeds half of ``caucus_size``, in which case another round follows. Every seat
    won in a Wahlkreis is kept throughout.
    """

    protocol: tuple[SerializeAsAny[AllocationStep], ...] = Field(
        min_length=1,
        description="The allocation of one chamber size, run first and again for each raised size, e.g. seat total, apportionment, deduction.",
    )
    factor: int = Field(
        default=2,
        ge=1,
        description="How many seats the chamber size grows by per seat of overhang, e.g. 2.",
    )
    full_rounds: int = Field(
        default=2,
        ge=0,
        description="How many rounds are repeated whatever the overhang.",
    )
    caucus_size: CaucusSize | None = Field(
        default=None,
        description=(
            "The caucus size limiting further rounds; ``None`` for no further rounds "
            "after the full ones."
        ),
    )

    @property
    def reads(self) -> frozenset[str]:
        extra = self.caucus_size.reads if self.caucus_size else frozenset()
        return _loop_reads(self.protocol) | (extra - written_by(self.protocol))

    @property
    def optional_reads(self) -> frozenset[str]:
        return outside_reads(self.protocol, optional=True)

    @property
    def writes(self) -> frozenset[str]:
        return written_by(self.protocol) | {"chamber_size"}

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {"caucus_size": (("seats", "seat_total"),)} if self.caucus_size else {}

    def _apply(self, allocation: Allocation) -> Allocation:
        allocation = _run(self.protocol, allocation)
        rounds = 0
        while excess := sum(n for _, n in allocation.overhang or ()):
            if rounds >= self.full_rounds:
                limit = self.caucus_size.seats(allocation) if self.caucus_size else None
                if limit is None or 2 * excess <= limit:
                    break
            size = (allocation.chamber_size or 0) + self.factor * excess
            allocation = _run(self.protocol, allocation.with_values(chamber_size=size))
            rounds += 1
        return allocation


class RaiseUntilBalanced(AllocationStep):
    """Allocate the seats of the chamber size with ``protocol``; then, while a party holds
    Überhang (``overhang``), raise the ``chamber_size`` one seat at a time and allocate
    again, until every party's entitlement covers its Wahlkreis seats: the other parties
    get Ausgleichsmandate. The loop holds its allocation, so a law writes it once.

    As in Sec. 58 (6) LKWG M-V. The Ausgleichsmandate are the seats the chamber gains
    beyond the chamber size plus the Überhang of the first allocation; with ``limit`` set, the
    chamber size is not raised past the point where they would exceed ``limit`` times that
    Überhang, and Überhang left then is kept. With ``has_odd_size``, a raised chamber
    of an even number of seats gains one more, and the chamber size is allocated again.

    The law does not say what happens when the odd seat brings back an Überhang, which
    Hare/Niemeyer can do, since it is not house-monotone; read here, the Überhang is
    then kept and the chamber size is not raised again.
    """

    protocol: tuple[SerializeAsAny[AllocationStep], ...] = Field(
        min_length=1,
        description="The allocation of one chamber size, run first and again for each raised size, e.g. seat total, apportionment, deduction.",
    )
    limit: int | None = Field(
        default=None,
        ge=0,
        description=(
            "The Ausgleichsmandate allowed per seat of Überhang, e.g. 2; ``None`` for no limit."
        ),
    )
    has_odd_size: bool = Field(
        default=False,
        description="Whether a raised chamber of an even number of seats gains one more.",
    )

    @property
    def reads(self) -> frozenset[str]:
        return _loop_reads(self.protocol)

    @property
    def optional_reads(self) -> frozenset[str]:
        return outside_reads(self.protocol, optional=True)

    @property
    def writes(self) -> frozenset[str]:
        return written_by(self.protocol) | {"chamber_size"}

    def _apply(self, allocation: Allocation) -> Allocation:
        allocation = _run(self.protocol, allocation)
        first = _overhang(allocation)
        if not first:
            return allocation
        base = (allocation.chamber_size or 0) + first
        cap = None if self.limit is None else self.limit * first
        while _overhang(allocation):
            raised = self._allocate(allocation, (allocation.chamber_size or 0) + 1)
            if cap is not None and _chamber_size(raised) - base > cap:
                break
            allocation = raised
        if self.has_odd_size and _chamber_size(allocation) % 2 == 0:
            allocation = self._allocate(allocation, (allocation.chamber_size or 0) + 1)
        return allocation

    def _allocate(self, allocation: Allocation, size: int) -> Allocation:
        return _run(self.protocol, allocation.with_values(chamber_size=size))


def _run(protocol: AllocationProtocol, allocation: Allocation) -> Allocation:
    for step in protocol:
        allocation = step.apply(allocation)
    return allocation


def _loop_reads(protocol: AllocationProtocol) -> frozenset[str]:
    """What a loop needs: what its protocol needs, and the chamber size it raises; the
    ``overhang`` it is driven by comes from its own first run."""
    return outside_reads(protocol) | {"chamber_size"}


def _overhang(allocation: Allocation) -> int:
    return sum(n for _, n in allocation.overhang or ())


def _chamber_size(allocation: Allocation) -> int:
    return (allocation.chamber_size or 0) + _overhang(allocation)
