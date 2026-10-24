"""Overhang: raising the chamber size when parties win more units than their
entitlement, and allocating again. Two ways a law does it: by a multiple of the overhang
for a few rounds (:class:`RaiseByOverhang`; the Mehrsitze of Sec. 35 (8), (8a) LWG LSA),
or a seat at a time until it is balanced (:class:`RaiseUntilBalanced`; the Überhang- and
Ausgleichsmandate of Sec. 58 (6) LKWG M-V). :class:`SetCaucusSize` (and Sec. 35 (8a)
LWG LSA's :class:`SetCaucusSizeFromAllVotes`) is a step for the block the first repeats:
it measures the yardstick for whether another round is due."""

from __future__ import annotations

from fractions import Fraction

from pydantic import Field, SerializeAsAny

from wahlwerk.apportionment.fictitious import FictitiousParty
from wahlwerk.apportionment.increment import Increment
from wahlwerk.apportionment.quota import Quota
from wahlwerk.ids import LevelName, Slug
from wahlwerk.process.allocation.base import (
    Allocation,
    AllocationProtocol,
    AllocationStep,
    Column,
    counts_fact,
    outside_reads,
    written_by,
)

__all__ = [
    "RaiseByOverhang",
    "RaiseChamberSize",
    "RaiseUntilBalanced",
    "SetCaucusSize",
    "SetCaucusSizeFromAllVotes",
]


class SetCaucusSize(AllocationStep):
    """Set ``caucus_size``: the seats a party needs for a caucus (a Fraktion), measured as
    the seats a ``fictitious`` party would at least win at this stage of the allocation,
    with its share of the votes the seats are divided by (the ``by`` table). Put in the
    block a :class:`RaiseByOverhang` repeats, it is measured again each round, and the
    loop asks for another round only while the overhang left exceeds half of it.

    How: ``quota`` gives the votes one of the ``seats_to_apportion`` seats is worth among
    the votes counted; the caucus size is the whole seats the fictitious party's votes
    make of it ("at least": a remainder seat is not certain). With a Hare quota that is
    the whole part of ``share`` times the seats. Sec. 35 (8a) LWG LSA measures the share
    of all valid votes instead: :class:`SetCaucusSizeFromAllVotes`.
    """

    fictitious: FictitiousParty = Field(
        description="The party it measures with, e.g. ``FictitiousParty(share=Fraction(5, 100))``.",
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
    by: Column = Field(
        default="eligible party",
        description=(
            "Whose votes the seats are divided by: the parties past the threshold "
            "(``eligible party``), or, with no threshold, every ``party``."
        ),
    )

    @property
    def inputs(self) -> dict[str, str]:
        return {
            "votes": counts_fact(self.section, self.level, self.by),
            "seats": "seats_to_apportion",
        }

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"caucus_size"})

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {
            "fictitious": (("total", "the votes counted"),),
            "quota": (
                ("part", "the fictitious party's votes"),
                ("votes", "the votes counted"),
                ("seats", "seats"),
            ),
        }

    def _counted(self, allocation: Allocation) -> tuple[Fraction, Fraction]:
        """The fictitious party's votes, and the votes counted with them."""
        counted = Fraction(sum(allocation.count(self.section, self.level, self.by).per_column().values()))
        return self.fictitious.votes(counted), counted

    def _apply(self, allocation: Allocation) -> Allocation:
        part, counted = self._counted(allocation)
        if not counted or not allocation.seats_to_apportion:
            return allocation.with_values(caucus_size=0)
        seats = self.quota.whole_seats(part, counted, allocation.seats_to_apportion)
        return allocation.with_values(caucus_size=seats)


class SetCaucusSizeFromAllVotes(SetCaucusSize):
    """Set ``caucus_size`` from all valid votes: :class:`SetCaucusSize` as Sec. 35 (8a)
    LWG LSA measures it. The fictitious party has its share of **all** valid votes in
    ``section`` ("fünf v. H. der im Land abgegebenen gültigen Zweitstimmen"), the votes
    of parties below the threshold included, and joins the parties the seats are divided
    by ("der jeweilige Stand der Verteilung der Abgeordnetensitze"). Against those its
    share is a little larger than its ``share``, by the votes below the threshold.

    The law does not say how the fictitious party enters the count (wahlrecht.de calls it
    unclear); joining the eligible parties is the reading, and it reproduces the official
    results of 2021 and 2026.
    """

    @property
    def inputs(self) -> dict[str, str]:
        return {
            "all": counts_fact(self.section, self.level, "party"),
            "votes": counts_fact(self.section, self.level, self.by),
            "seats": "seats_to_apportion",
        }

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {
            "fictitious": (("total", "all valid votes"),),
            "quota": (
                ("part", "the fictitious party's votes"),
                ("votes", "the votes counted and the fictitious party's"),
                ("seats", "seats"),
            ),
        }

    def _counted(self, allocation: Allocation) -> tuple[Fraction, Fraction]:
        every = sum(allocation.count(self.section, self.level, "party").per_column().values())
        counted = sum(allocation.count(self.section, self.level, self.by).per_column().values())
        part = self.fictitious.votes(every)
        return part, counted + part


class RaiseChamberSize(AllocationStep):
    """Raise the ``chamber_size`` for its ``overhang`` by ``increment`` (Sec. 35 (8)
    LWG LSA: twice the Mehrsitze, ``Increment(factor=2)``). The step a
    :class:`RaiseByOverhang` takes each round, before it allocates again."""

    increment: Increment = Field(
        default_factory=Increment,
        description="How much the chamber size grows per seat of overhang, e.g. ``Increment(factor=2)``.",
    )

    @property
    def inputs(self) -> dict[str, str]:
        return {"size": "chamber_size", "overhang": "overhang"}

    @property
    def writes(self) -> frozenset[str]:
        return frozenset({"chamber_size"})

    @property
    def passes(self) -> dict[str, tuple[tuple[str, str], ...]]:
        return {"increment": (("size", "size"), ("overhang", "overhang"))}

    def _apply(self, allocation: Allocation) -> Allocation:
        size = self.increment.of(allocation.chamber_size or 0, dict(allocation.overhang or ()))
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
