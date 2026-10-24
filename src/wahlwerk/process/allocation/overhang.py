"""Overhang: raising the chamber size when parties win more units than their
entitlement, and allocating again. Two ways a law does it: by a multiple of the overhang
for a few rounds (:class:`RaiseByOverhang`; the Mehrsitze of Sec. 35 (8), (8a) LWG LSA),
or a seat at a time until it is balanced (:class:`RaiseUntilBalanced`; the Überhang- and
Ausgleichsmandate of Sec. 58 (6) LKWG M-V). :class:`SetCaucusSize` is a step for the
block the first repeats: it measures the yardstick for whether another round is due."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.quota import Quota
from wahlwerk.calc import compensation
from wahlwerk.calc import quota as calc_quota
from wahlwerk.ids import LevelName, Slug
from wahlwerk.model import Share
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationProtocol,
    AllocationStep,
    counts_fact,
    eligible_fact,
    outside_reads,
    written_by,
)

__all__ = ["RaiseByOverhang", "RaiseChamberSize", "RaiseUntilBalanced", "SetCaucusSize"]


class SetCaucusSize(AllocationStep):
    """Set ``caucus_size``: the seats a party needs for a caucus (a Fraktion), measured as
    the seats a fictitious party would at least win with ``share`` of all valid votes in
    ``section``, at this stage of the allocation (Sec. 35 (8a) LWG LSA). Put in the block
    a :class:`RaiseByOverhang` repeats, it is measured again each round, and the loop
    asks for another round only while the overhang left exceeds half of it.

    How: the fictitious party joins the eligible parties with ``share`` of all valid
    votes; ``quota`` gives the votes one of the ``seats_to_apportion`` seats is worth among them;
    the caucus size is the whole seats the fictitious party's votes make of it. The law
    does not say how the fictitious party enters the count (wahlrecht.de calls it
    unclear); this is the reading, and "at least" is the whole part, since a remainder
    seat is not certain.
    """

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (calc_quota.whole_seats,)

    share: Share = Field(
        description="The fictitious party's share of all valid votes, e.g. ``Fraction(5, 100)``.",
    )
    section: Slug = Field(
        description="The vote it is measured on, e.g. ``zweitstimme``.",
    )
    level: LevelName = Field(
        description="The level the votes are summed at, e.g. ``land``.",
    )
    quota: SerializeAsAny[Quota] = Field(
        description="What one seat is worth among the votes counted, e.g. ``HareQuota()``.",
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
        return frozenset({"caucus_size"})

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {
            "quota": (
                ("votes", "votes of the eligible parties and of the fictitious one"),
                ("seats", "seats"),
            ),
            "": (("votes", "the fictitious party's"), ("quota", "the quota")),
        }

    def _apply(self, allocation: Allocation) -> Allocation:
        votes = allocation.count(self.section, self.level, "party").per_column()
        eligible = allocation.eligible(self.section)
        fictitious = self.share * sum(votes.values())
        counted = sum(n for party, n in votes.items() if party in eligible) + fictitious
        if not counted or not allocation.seats_to_apportion:
            return allocation.with_values(caucus_size=0)
        (whole_seats,) = self.formulas
        seats: int = whole_seats(fictitious, self.quota.of(counted, allocation.seats_to_apportion))
        return allocation.with_values(caucus_size=seats)


class RaiseChamberSize(AllocationStep):
    """Raise the ``chamber_size`` by ``factor`` seats per seat of ``overhang`` (Sec. 35 (8)
    LWG LSA: twice the Mehrsitze). The step a :class:`RaiseByOverhang` takes each round,
    before it allocates again."""

    formulas: ClassVar[tuple[Callable[..., Any], ...]] = (compensation.raised,)

    factor: int = Field(
        default=1,
        ge=1,
        description="How many seats the chamber size grows by per seat of overhang, e.g. 2.",
    )

    @property
    def inputs(self) -> dict[str, str]:
        return {"size": "chamber_size", "overhang": "overhang"}

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"chamber_size"})

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {"": (("size", "chamber_size"), ("overhang", "per party"), ("factor", str(self.factor)))}

    def _apply(self, allocation: Allocation) -> Allocation:
        (raised,) = self.formulas
        size: int = raised(allocation.chamber_size or 0, dict(allocation.overhang or ()), self.factor)
        return allocation.with_values(chamber_size=size)


class RaiseByOverhang(AllocationStep):
    """While the allocation leaves overhang to balance, run ``protocol`` again: usually
    raise the chamber size (:class:`RaiseChamberSize`), allocate its seats, and measure
    the caucus size. A law runs the allocation once before it; with no overhang the loop
    does nothing, and the chamber is filled from the lists.

    The condition, as in Sec. 35 (8) LWG LSA: in the first ``full_rounds`` rounds, any
    overhang is balanced; after that only overhang exceeding half the ``caucus_size``
    the last round measured (a :class:`SetCaucusSize` step); overhang left then is kept
    unbalanced (the chamber has that many seats more). Every seat won in a unit is kept
    throughout.
    """

    protocol: tuple[SerializeAsAny[AllocationStep], ...] = Field(
        min_length=1,
        description="What one round does, e.g. raise the chamber size, allocate, measure the caucus size.",
    )
    full_rounds: int = Field(
        default=2,
        ge=0,
        description="How many rounds balance any overhang, before the caucus size limits them.",
    )

    @property
    def condition(self) -> str:
        """When another round runs, in words."""
        return (
            f"while overhang > 0; after {self.full_rounds} rounds, "
            "while 2 × overhang > caucus_size"
        )

    @property
    def reads(self) -> frozenset[str]:
        return outside_reads(self.protocol) | {"overhang"}

    @property
    def optional_reads(self) -> frozenset[str]:
        return outside_reads(self.protocol, optional=True) | {"caucus_size"}

    @property
    def writes(self) -> frozenset[str]:
        return written_by(self.protocol)

    def _is_due(self, allocation: Allocation, done: int) -> bool:
        excess = _overhang(allocation)
        if not excess:
            return False
        if done < self.full_rounds:
            return True
        limit = allocation.caucus_size  # measured by the last round, if the law does
        return limit is not None and 2 * excess > limit

    def rounds(self, allocation: Allocation) -> tuple[Allocation, ...]:
        """The allocation it starts from, then one per round run. The last is the
        result; the ones before show how it was reached (what a drawing of the rule
        needs). ``allocation`` must hold what the step reads."""
        missing = self.reads - allocation.facts
        if missing:
            raise ValueError(f"{type(self).__name__} reads {sorted(missing)}, which are not established")
        done = [allocation]
        while self._is_due(done[-1], len(done) - 1):
            done.append(_run(self.protocol, done[-1]))
        return tuple(done)

    def _apply(self, allocation: Allocation) -> Allocation:
        return self.rounds(allocation)[-1]


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
        description="The allocation of one chamber size, run first and again for each raised size, e.g. seats to apportion, apportionment, deduction.",
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

    def rounds(self, allocation: Allocation) -> tuple[Allocation, ...]:
        """Each run of the block that is kept, in order: the first at the chamber size
        given, then one per raised size (and the odd seat). The last is the result."""
        missing = self.reads - allocation.facts
        if missing:
            raise ValueError(f"{type(self).__name__} reads {sorted(missing)}, which are not established")
        done = [_run(self.protocol, allocation)]
        first = _overhang(done[0])
        if not first:
            return tuple(done)
        base = (done[0].chamber_size or 0) + first
        cap = None if self.limit is None else self.limit * first
        while _overhang(done[-1]):
            raised = self._allocate(done[-1], (done[-1].chamber_size or 0) + 1)
            if cap is not None and _chamber_size(raised) - base > cap:
                break
            done.append(raised)
        if self.has_odd_size and _chamber_size(done[-1]) % 2 == 0:
            done.append(self._allocate(done[-1], (done[-1].chamber_size or 0) + 1))
        return tuple(done)

    def _apply(self, allocation: Allocation) -> Allocation:
        return self.rounds(allocation)[-1]

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
